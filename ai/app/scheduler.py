from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import numpy as np
from ortools.sat.python import cp_model
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def map_solver_day_to_timestamp(start_date: datetime, solver_day_index: int):
  """Converts OR-Tools day index into a timestamp for scheduling purposes."""
  
  # Calculate the exact calendar date
  local_tz = ZoneInfo("America/Toronto")
  if start_date.tzinfo is None:
    start_date = start_date.replace(tzinfo=local_tz)

  target_date = start_date + timedelta(days=solver_day_index)

  # Apply standard shift defaults (i.e 8:00 AM - 12 PM - lasts 4 hours)
  scheduled_start = target_date.replace(hour=8, minute=0, second=0, microsecond=0)
  scheduled_end = target_date.replace(hour=12, minute=0, second=0, microsecond=0)

  return scheduled_start, scheduled_end

def optimize_maintenance_schedule(predictions: list) -> dict:
    """Takes a list of predictionOutput dictionaries and returns the optimal calendar maintenance schedule."""

    model = cp_model.CpModel()
    equipment_dict = {}
    scheduled_days = {}

    for item in predictions:
        equipment_id = item.equipment_id
        asset_tag = item.asset_tag
        risk_level = item.risk_level
        projection_years = item.projection_years

        # Store equipment details in a dictionary for easy access later
        equipment_dict[asset_tag] = {
            "equipment_id": equipment_id,
            "risk_level": risk_level,
            "projection_years": projection_years
        }

        # Determine scheduling urgency window based on risk level
        if risk_level == "high":
            latest_safe_day = 7  # Service within 1 week
        elif risk_level == "medium":
            latest_safe_day = 30  # Service within 1 month
        else:
            latest_safe_day = (
                projection_years * 365
            )  # low risk - routine maintenance

        scheduled_days[asset_tag] = model.NewIntVar(
            1, latest_safe_day, f"day_{asset_tag}"
        )

    # Ensure equipments are not serviced on the exact same day
    all_vars = list(scheduled_days.values())
    if len(all_vars) > 1:
        model.AddAllDifferent(all_vars)

    # Minimize total delay
    model.Minimize(sum(scheduled_days.values()))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    final_schedule = {}

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for asset_tag, var in scheduled_days.items():
            solver_day_offset = solver.Value(var)

            # Convert integer day to an actual date string
            scheduled_start, scheduled_end = map_solver_day_to_timestamp(datetime.now(), solver_day_offset)

            final_schedule[asset_tag] = {
                "equipment_id": equipment_dict[asset_tag]["equipment_id"],
                "asset_tag": asset_tag,
                "scheduled_start_time": scheduled_start,
                "scheduled_end_time": scheduled_end,
                "status": "scheduled",
                "status_msg": None,
                "priority_score": equipment_dict[asset_tag]["projection_years"]  # Using projection_years as a proxy for priority
            }
    else:
        # Figure out why the scheduling model failed
        status_str = solver.status_name(status)
        
        if status == cp_model.INFEASIBLE:
            # Hard contradiction exists
            status_msg = "Equipment Maintenance Scheduler: Conflicting constraints detected (overlapping equipment bookings or impossible technician time windows)."
        elif status == cp_model.UNKNOWN:
            status_msg = "Equipment Maintenance Scheduler timed out: The schedule space is too complex to resolve within the allowed time limit."
        elif status == cp_model.MODEL_INVALID:
            # Model itself is invalid (i.e constraints)
            status_msg = "Equipment Maintenance Scheduler failed: Malformed model structure or invalid variable bounds."
        else:
            status_msg = f"Equipment Maintenance Scheduler failed with unexpected status: {status_str}"
            
        for asset_tag in scheduled_days:
            final_schedule[asset_tag] = {
                "equipment_id": equipment_dict[asset_tag]["equipment_id"],
                "asset_tag": asset_tag,
                "scheduled_start_time": None,
                "scheduled_end_time": None,
                "status": "failed",
                "status_msg": status_msg,
                "priority_score": None
            }

    return final_schedule