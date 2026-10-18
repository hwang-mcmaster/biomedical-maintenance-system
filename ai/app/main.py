r"""
Biomedical Maintenance AI service.

Run from the ai folder:
    .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

Endpoints
  GET  /api/ai/health          service status (and whether the model is loaded)
  POST /api/ai/predict         one unit  -> predicted annual cost, repair-intensity risk, value view
  POST /api/ai/fleet-summary   many units -> per-unit results plus fleet totals for the dashboard

The model is trained by app/train.py on synthetic data. The risk level is a
repair-intensity indicator, NOT a failure probability.
"""
import json
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_FILE = BASE_DIR / "models" / "cost_model.joblib"
META_FILE = BASE_DIR / "models" / "model_metadata.json"

app = FastAPI(title="Biomedical Maintenance AI Service")


# ---------- model loading ----------

@lru_cache(maxsize=1)
def load_model():
    if not MODEL_FILE.exists() or not META_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="Model files not found. Run app/train.py first (it writes the models folder).",
        )
    model = joblib.load(MODEL_FILE)
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    return model, meta


# ---------- request / response models ----------

class AssetIn(BaseModel):
    asset_tag: Optional[str] = Field(None, examples=["CED-10000"])
    manufacturer: str = Field(..., examples=["Getinge SERVOi"])
    age_years: float = Field(..., gt=0, examples=[23.38])
    repair_events: int = Field(..., ge=0, examples=[19])
    cumulative_cost_to_date: Optional[float] = Field(None, ge=0, examples=[9678.12])
    assumed_replacement_cost: Optional[float] = Field(None, gt=0, examples=[20000.0])
    projection_years: int = Field(5, ge=1, le=20)


class PredictionOut(BaseModel):
    asset_tag: Optional[str]
    predicted_annual_cost: float
    cost_error_range: float          # typical error (cross-validated MAE), +/- dollars per year
    repair_rate_per_year: float
    risk_score: float                # 0-1: share of the training fleet with a repair rate at or below this unit
    risk_level: str                  # low / medium / high repair intensity
    cumulative_cost_to_date: Optional[float]
    projected_cost_next_years: float
    projection_years: int
    assumed_replacement_cost: Optional[float]
    maintenance_to_replacement_ratio: Optional[float]
    warnings: List[str]


class FleetIn(BaseModel):
    assets: List[AssetIn] = Field(..., min_length=1)


class FleetSummaryOut(BaseModel):
    n_units: int
    total_predicted_annual_cost: float
    average_predicted_annual_cost: float
    units_per_risk_level: dict
    cost_by_manufacturer: dict
    most_repair_intensive_units: List[PredictionOut]
    predictions: List[PredictionOut]


# ---------- prediction logic ----------

def predict_one(asset: AssetIn) -> PredictionOut:
    model, meta = load_model()
    repair_rate = asset.repair_events / asset.age_years

    row = pd.DataFrame([{
        "manufacturer": asset.manufacturer.strip(),
        "age_years": asset.age_years,
        "repair_events": asset.repair_events,
        "repair_rate": repair_rate,
    }])[meta["features"]]
    annual = max(0.0, float(model.predict(row)[0]))

    warnings = []
    if "manufacturer" in meta["features"] and asset.manufacturer.strip() not in meta["manufacturers"]:
        warnings.append(
            f"Manufacturer '{asset.manufacturer}' was not in the training data "
            f"({', '.join(meta['manufacturers'])}); its effect was ignored."
        )

    fleet = meta["fleet_repair_rates"]
    risk_score = bisect_right(fleet, repair_rate) / len(fleet)
    cut = meta["repair_rate_cutoffs"]
    if repair_rate < cut["low_below"]:
        level = "low"
    elif repair_rate >= cut["high_from"]:
        level = "high"
    else:
        level = "medium"

    ratio = None
    if asset.cumulative_cost_to_date is not None and asset.assumed_replacement_cost:
        ratio = asset.cumulative_cost_to_date / asset.assumed_replacement_cost

    return PredictionOut(
        asset_tag=asset.asset_tag,
        predicted_annual_cost=round(annual, 2),
        cost_error_range=round(meta["selected_mae"], 2),
        repair_rate_per_year=round(repair_rate, 4),
        risk_score=round(risk_score, 3),
        risk_level=level,
        cumulative_cost_to_date=asset.cumulative_cost_to_date,
        projected_cost_next_years=round(annual * asset.projection_years, 2),
        projection_years=asset.projection_years,
        assumed_replacement_cost=asset.assumed_replacement_cost,
        maintenance_to_replacement_ratio=None if ratio is None else round(ratio, 3),
        warnings=warnings,
    )


# ---------- endpoints ----------

@app.get("/api/ai/health")
def health():
    ready = MODEL_FILE.exists() and META_FILE.exists()
    return {"status": "ok", "message": "AI service is running", "model_loaded": ready}


@app.post("/api/ai/predict", response_model=PredictionOut)
def predict(asset: AssetIn):
    return predict_one(asset)


@app.post("/api/ai/fleet-summary", response_model=FleetSummaryOut)
def fleet_summary(fleet: FleetIn):
    preds = [predict_one(a) for a in fleet.assets]
    total = sum(p.predicted_annual_cost for p in preds)

    levels = {"low": 0, "medium": 0, "high": 0}
    for p in preds:
        levels[p.risk_level] += 1

    by_maker = {}
    for a, p in zip(fleet.assets, preds):
        by_maker[a.manufacturer] = round(by_maker.get(a.manufacturer, 0.0) + p.predicted_annual_cost, 2)

    top = sorted(preds, key=lambda p: p.repair_rate_per_year, reverse=True)[:5]
    return FleetSummaryOut(
        n_units=len(preds),
        total_predicted_annual_cost=round(total, 2),
        average_predicted_annual_cost=round(total / len(preds), 2),
        units_per_risk_level=levels,
        cost_by_manufacturer=by_maker,
        most_repair_intensive_units=top,
        predictions=preds,
    )
