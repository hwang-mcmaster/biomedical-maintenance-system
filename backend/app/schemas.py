from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, computed_field

from .calculations import reference_date, exact_age, two_places, annual_average

Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class EquipmentData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_tag: Text50
    serial_number: Text100
    manufacturer: Text100
    in_service_date: date
    repair_events: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = 0
    total_historical_cost: Money = Decimal('0.00')


class EquipmentCreate(EquipmentData):
    @field_validator('in_service_date')
    @classmethod
    def before_today(cls, value):
        if value >= reference_date():
            raise ValueError('In-service date must be before today.')
        return value


class Equipment(EquipmentData):
    id: UUID
    calculated_as_of: date = Field(default_factory=reference_date)

    @computed_field
    @property
    def age_years(self) -> Decimal:
        return two_places(exact_age(self.in_service_date, self.calculated_as_of))

    @computed_field
    @property
    def avg_annual_cost(self) -> Decimal | None:
        age = exact_age(self.in_service_date, self.calculated_as_of)
        return annual_average(self.total_historical_cost, age)


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
