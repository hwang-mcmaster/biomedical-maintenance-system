"""Call the team's existing AI service; keep model dependencies out of the API."""
import os
from decimal import Decimal
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from .schemas import Assessment, Prediction
from .calculations import exact_age, two_places

LIMITATION = ('Prototype trained on synthetic ventilator data. Confirm that this item belongs to the ventilator fleet; '
              'device type is not recorded. Repair intensity is not failure probability or clinical safety. '
              'Recommendations require engineering review.')
RECOMMENDATIONS = {
    'low': 'Keep this item in the routine maintenance review queue; verify service records and manufacturer guidance.',
    'medium': 'Review repair history and planned maintenance with the biomedical engineering team.',
    'high': 'Prioritize an engineering review of repeated repairs and lifecycle costs before making maintenance or replacement decisions.',
}


def assess_equipment(device):
    age = exact_age(device.in_service_date, device.calculated_as_of)
    if age <= 0:
        raise HTTPException(422, 'Assessment requires a positive elapsed age. Check the in-service date.')
    payload = {
        'asset_tag': device.asset_tag, 'manufacturer': device.manufacturer,
        'age_years': float(age), 'repair_events': device.repair_events,
        'cumulative_cost_to_date': float(device.total_historical_cost),
        'projection_years': 5,
    }
    url = os.getenv('AI_SERVICE_URL', 'http://127.0.0.1:8001').rstrip('/')
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(f'{url}/api/ai/predict', json=payload)
            response.raise_for_status()
            prediction = Prediction.model_validate(response.json())
    except (httpx.HTTPError, ValueError, ValidationError):
        raise HTTPException(503, 'Assessment service unavailable. Check that the AI service and its model are running, then retry.') from None
    # Also normalize older AI-service responses so annual x horizon matches the UI.
    annual_amount = two_places(Decimal(str(prediction.predicted_annual_cost)))
    prediction.predicted_annual_cost = float(annual_amount)
    prediction.projected_cost_next_years = float(two_places(annual_amount * prediction.projection_years))
    low, high = prediction.training_repair_rate_min, prediction.training_repair_rate_max
    if low is None or high is None or low > high:
        prediction.warnings.append('Training repair-rate range is unavailable; range applicability could not be checked.')
    else:
        # Metadata rates are recorded to six decimals. Compare at that precision.
        rate = round(device.repair_events / float(age), 6)
        if rate < low or rate > high:
            prediction.warnings.append(
                f'Repair rate ({rate:.3f} repairs/year) is outside the observed training range '
                f'({low:.3f} to {high:.3f} repairs/year). This estimate is an extrapolation; review model applicability.'
            )
    prediction.warnings = list(dict.fromkeys(prediction.warnings))
    return Assessment(
        equipment_id=device.id, risk_score=prediction.risk_score,
        risk_level=prediction.risk_level, assessed_at=datetime.now(timezone.utc),
        method='AI maintenance-cost model + repair-intensity rules',
        recommendation=RECOMMENDATIONS[prediction.risk_level],
        limitation=LIMITATION, prediction=prediction,
    )
