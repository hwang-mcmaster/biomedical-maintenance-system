from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class EquipmentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_tag: Text50
    serial_number: Text100
    manufacturer: Text100
    in_service_date: date
    # Dataset snapshots: preserve supplied values, do not derive them from today's date.
    age_years: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=3)]
    repair_events: Annotated[int, Field(strict=True, ge=0, le=2147483647)]
    total_historical_cost: Money
    avg_annual_cost: Money

    @field_validator('in_service_date')
    @classmethod
    def not_in_future(cls, value):
        if value > date.today():
            raise ValueError('In-service date cannot be in the future.')
        return value


class Equipment(EquipmentCreate):
    id: UUID


class Prediction(BaseModel):
    asset_tag: str | None
    predicted_annual_cost: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    cost_error_range: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    repair_rate_per_year: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    risk_score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    risk_level: Literal['low', 'medium', 'high']
    cumulative_cost_to_date: float | None
    projected_cost_next_years: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    projection_years: Annotated[int, Field(ge=1, le=20)]
    assumed_replacement_cost: float | None
    maintenance_to_replacement_ratio: float | None
    warnings: list[str]


class Assessment(BaseModel):
    equipment_id: UUID
    risk_score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, description='Relative repair-intensity percentile from 0 to 1; not failure probability.')]
    risk_level: Literal['low', 'medium', 'high']
    assessed_at: datetime
    method: str
    recommendation: str
    limitation: str
    prediction: Prediction
