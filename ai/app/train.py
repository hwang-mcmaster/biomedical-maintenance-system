r"""
Train the maintenance-cost model for the ventilator fleet.

Run from the ai folder:
    .\venv\Scripts\python.exe app\train.py

Reads  : data/ventilator_inventory.csv
Writes : models/cost_model.joblib and models/model_metadata.json

Model scope (agreed with the team):
  - Target  : avg_annual_cost  (average annual maintenance cost, $)
  - Inputs  : age_years, manufacturer, repair_events, repair_rate (= events per year)
  - NOT used: total_historical_cost (avg_annual_cost = total cost / age, so using it
              would leak the answer), serial number, asset tag, in-service date.
Several small feature sets are compared with leave-one-out cross-validation and the
one with the lowest error is saved.
"""
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "ventilator_inventory.csv"
MODEL_FILE = BASE_DIR / "models" / "cost_model.joblib"
META_FILE = BASE_DIR / "models" / "model_metadata.json"

CATEGORICAL = ["manufacturer"]
TARGET = "avg_annual_cost"
REQUIRED = ["manufacturer", "age_years", "repair_events", TARGET]

# Candidate feature sets (kept small on purpose: only a few dozen units).
FEATURE_SETS = {
    "age + manufacturer": ["manufacturer", "age_years"],
    "age + manufacturer + repair events": ["manufacturer", "age_years", "repair_events"],
    "repair rate + manufacturer": ["manufacturer", "repair_rate"],
    "age + repair rate + manufacturer": ["manufacturer", "age_years", "repair_rate"],
}


def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise SystemExit(f"Data file not found: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing columns: {missing}. Found: {list(df.columns)}")
    df["manufacturer"] = df["manufacturer"].astype(str).str.strip()
    df = df.dropna(subset=REQUIRED)
    df = df[df["age_years"] > 0].copy()
    df["repair_rate"] = df["repair_events"] / df["age_years"]  # repair events per year
    return df.reset_index(drop=True)


def make_pipeline(features, estimator) -> Pipeline:
    cat = [f for f in features if f in CATEGORICAL]
    num = [f for f in features if f not in CATEGORICAL]
    parts = []
    if cat:
        parts.append(("cat", OneHotEncoder(handle_unknown="ignore"), cat))
    if num:
        parts.append(("num", "passthrough", num))
    return Pipeline([("prep", ColumnTransformer(parts)), ("model", estimator)])


def metrics(y_true, y_pred) -> dict:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
    }


def main() -> None:
    df = load_data()
    y = df[TARGET]

    print(f"Loaded {len(df)} units from {DATA_FILE.name}")
    print(df.groupby("manufacturer").size().to_string(), "\n")
    print(f"Target {TARGET}: mean ${y.mean():.2f}, min ${y.min():.2f}, max ${y.max():.2f}\n")

    # Leave-one-out cross-validation: each unit is predicted by a model that never saw it.
    print("Leave-one-out cross-validation (error on units the model has not seen):")
    results = {}
    base_pred = cross_val_predict(
        make_pipeline(["age_years"], DummyRegressor(strategy="mean")),
        df[["age_years"]], y, cv=LeaveOneOut())
    results["Baseline (always the fleet mean)"] = metrics(y, base_pred)
    for name, feats in FEATURE_SETS.items():
        pred = cross_val_predict(make_pipeline(feats, LinearRegression()),
                                 df[feats], y, cv=LeaveOneOut())
        results[name] = metrics(y, pred)
    for name, r in results.items():
        print(f"  {name:<38} MAE ${r['MAE']:.2f}  RMSE ${r['RMSE']:.2f}  R2 {r['R2']:.3f}")

    # Pick the feature set with the lowest cross-validated RMSE.
    best_name = min(FEATURE_SETS, key=lambda n: results[n]["RMSE"])
    best_feats = FEATURE_SETS[best_name]
    print(f"\nSelected feature set: {best_name}  ->  {best_feats}")

    final = make_pipeline(best_feats, LinearRegression()).fit(df[best_feats], y)
    names = final.named_steps["prep"].get_feature_names_out()
    coefs = final.named_steps["model"].coef_
    print("Final model coefficients (effect on annual cost, $):")
    for n, c in zip(names, coefs):
        print(f"  {n:<32} {c:+.3f}")
    print(f"  {'intercept':<32} {final.named_steps['model'].intercept_:+.3f}")

    # Risk flag cut-offs: tertiles of repair_rate across the fleet.
    low_cut, high_cut = np.percentile(df["repair_rate"], [100 / 3, 200 / 3])

    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, MODEL_FILE)
    meta = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_units": int(len(df)),
        "target": TARGET,
        "selected_feature_set": best_name,
        "features": best_feats,
        "manufacturers": sorted(df["manufacturer"].unique().tolist()),
        "repair_rate_cutoffs": {"low_below": float(low_cut), "high_from": float(high_cut)},
        "fleet_repair_rates": sorted(round(float(v), 6) for v in df["repair_rate"]),
        "selected_mae": results[best_name]["MAE"],
        "cv_metrics_leave_one_out": results,
        "note": "Synthetic data. Repair-intensity risk flag, not a failure probability.",
    }
    META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nSaved model    -> {MODEL_FILE}")
    print(f"Saved metadata -> {META_FILE}")


if __name__ == "__main__":
    main()
