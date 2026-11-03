r"""
Recompute age_years and avg_annual_cost in the dataset for a chosen reference date.

Run from the ai folder:
    .\venv\Scripts\python.exe app\set_reference_date.py 2026-09-20

Age = days from in_service_date to the reference date, divided by 365.25, rounded
to 2 places. avg_annual_cost = total_historical_cost / age_years, rounded to 2
places. Retrain afterwards with app/train.py.
"""
import sys
from pathlib import Path

import pandas as pd

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "ventilator_inventory.csv"


def main(reference_date: str) -> None:
    ref = pd.Timestamp(reference_date)
    df = pd.read_csv(DATA_FILE, parse_dates=["in_service_date"])
    if (df["in_service_date"] >= ref).any():
        raise SystemExit("Some in_service_date values are on or after the reference date.")

    old = df[["age_years", "avg_annual_cost"]].copy()
    df["age_years"] = ((ref - df["in_service_date"]).dt.days / 365.25).round(2)
    df["avg_annual_cost"] = (df["total_historical_cost"] / df["age_years"]).round(2)
    df["in_service_date"] = df["in_service_date"].dt.strftime("%Y-%m-%d")
    df.to_csv(DATA_FILE, index=False)       
    (DATA_FILE.parent / "reference_date.txt").write_text(reference_date + "\n", encoding="utf-8")


    d_age = df["age_years"] - old["age_years"]
    d_cost = df["avg_annual_cost"] - old["avg_annual_cost"]
    print(f"Reference date {reference_date}: {len(df)} rows updated")
    print(f"age_years change: {d_age.min():.2f} to {d_age.max():.2f}")
    print(f"avg_annual_cost change: {d_cost.min():.2f} to {d_cost.max():.2f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python app/set_reference_date.py YYYY-MM-DD")
    main(sys.argv[1])