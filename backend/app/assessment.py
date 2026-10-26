"""Call the team's existing AI service; keep model dependencies out of the API."""
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from .schemas import Assessment, Prediction
from .calculations import exact_age

LIMITATION = ('Prototype trained on synthetic ventilator data. Risk means relative repair intensity, '
              'not failure probability or clinical safety. Recommendations require engineering review.')
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
    prediction.warnings.insert(0, 'This dataset has no device-type field. Confirm that the item belongs to the ventilator fleet before interpreting this model output.')
    return Assessment(
        equipment_id=device.id, risk_score=prediction.risk_score,
        risk_level=prediction.risk_level, assessed_at=datetime.now(timezone.utc),
        method='AI maintenance-cost model + repair-intensity rules',
        recommendation=RECOMMENDATIONS[prediction.risk_level],
        limitation=LIMITATION, prediction=prediction,
    )
