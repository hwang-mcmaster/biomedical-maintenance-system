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
import httpx
from uuid import UUID
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from datetime import date
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from backend.app.repository import sweep_overdue_schedules, get_equipment_due_for_maintenance, save_optimized_maintenance_schedule
from .scheduler import optimize_maintenance_schedule
from backend.app.schemas import Equipment

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_FILE = BASE_DIR / "models" / "cost_model.joblib"
META_FILE = BASE_DIR / "models" / "model_metadata.json"

# Assumed replacement cost per model label, in CAD.
# None means no confirmed source yet. Used only when the request sends no
# replacement cost of its own.
REPLACEMENT_COST_CAD = {
    "Getinge SERVOi": {"cost": None, "source": "to be confirmed", "as_of": None},
    "Draeger V500": {"cost": None, "source": "to be confirmed", "as_of": None},
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_overdue_schedules()  # Check for overdue scheduled maintenance tasks when the app starts

    # Run the nightly job to optimize the maintenance schedule
    scheduler = AsyncIOScheduler()

    # We can later change this to a cron job that runs at a specific time
    # scheduler.add_job(run_schedule_optimizer, 
    #                   'cron', 
    #                   hour=2,
    #                   minute=0,
    #                   args=[
    #                       fleetSummaryOutObj.predictions
    #                     ],)

    scheduler.add_job(run_maintenance_schedule_optimizer, 
                          'interval', 
                          minutes=60)
    scheduler.start()
    
    yield

    scheduler.shutdown()

app = FastAPI(title="Biomedical Maintenance AI Service", lifespan=lifespan)

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

class MaintenanceScheduleRequest(BaseModel):
    equipment_id: UUID
    asset_tag: str
    risk_level: str
    projection_years: int

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

    replacement_cost = asset.assumed_replacement_cost
    if replacement_cost is None:
        ref = REPLACEMENT_COST_CAD.get(asset.manufacturer.strip())
        if ref and ref["cost"]:
            replacement_cost = ref["cost"]
            warnings.append(
                f"Replacement cost {ref['cost']:,.0f} CAD is an assumption for "
                f"{asset.manufacturer.strip()} (source: {ref['source']}, {ref['as_of']})."
            )

    ratio = None
    if asset.cumulative_cost_to_date is not None and replacement_cost:
        ratio = asset.cumulative_cost_to_date / replacement_cost
	
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
        assumed_replacement_cost=replacement_cost,
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

@app.post("/api/ai/optimize-schedule")
def run_maintenance_schedule_optimizer():
    raw_rows = get_equipment_due_for_maintenance()
    equipment_list = [Equipment(**row) for row in raw_rows]

    # Map the calculated equipment objects into AssetIn objects for the fleet summary
    assetInList: List[AssetIn] = [
        AssetIn(
            asset_tag=eq.asset_tag,
            manufacturer=eq.manufacturer,
            age_years=eq.age_years,
            repair_events=eq.repair_events,
            cumulative_cost_to_date=eq.total_historical_cost,
            assumed_replacement_cost=None,
            projection_years=5,  # default to 5 years
            )
            
        for eq in equipment_list
    ]

    fleetInObj = FleetIn(assets=assetInList)
    fleetSummaryOutObj = fleet_summary(fleetInObj)
    payload: list[MaintenanceScheduleRequest] = []

    # Using the predictions, create a list of MaintenanceScheduleRequest objects for the optimizer
    for pred in fleetSummaryOutObj.predictions:
        equipment = next((eq for eq in equipment_list if eq.asset_tag == pred.asset_tag), None)
        if equipment:
            payload.append(MaintenanceScheduleRequest(
                equipment_id=equipment.id,
                asset_tag=pred.asset_tag,
                risk_level=pred.risk_level,
                projection_years=pred.projection_years
            ))

    optimized_result = optimize_maintenance_schedule(payload)
    save_optimized_maintenance_schedule(optimized_result)  # Save the optimized schedule to the database
    print(f"Successfully saved optimized maintenance schedule for {len(optimized_result)} equipment items.")
    return {"status": "success", "schedule": optimized_result}