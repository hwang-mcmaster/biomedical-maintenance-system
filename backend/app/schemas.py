from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, computed_field

from .calculations import reference_date, exact_age, two_places, annual_average

Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
DEVICE_TYPES = ('Ventilator', 'Infusion Pump', 'Patient Monitor', 'Defibrillator', 'Other')
STATUSES = ('Operational', 'Under Maintenance', 'Inactive')
SCHEDULED_MAINTENANCE_STATUSES = Literal['pending', 'in_progress', 'scheduled', 'completed', 'cancelled', "incomplete", "failed"]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class EquipmentData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_tag: Text50
    serial_number: Text100
    manufacturer: Text100
    in_service_date: date
    repair_events: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = 0
    total_historical_cost: Money = Decimal('0.00')
    model_number: OptionalText | None = None
    model_name: OptionalText | None = None
    device_type: Literal['Ventilator', 'Infusion Pump', 'Patient Monitor', 'Defibrillator', 'Other'] | None = None
    firmware_version: Text50 | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] | None = None
    department: OptionalText | None = None
    department_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None = None
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    status: Literal['Operational', 'Under Maintenance', 'Inactive'] | None = None
    replacement_cost: Money | None = None
    expected_useful_life: Annotated[int, Field(strict=True, ge=1, le=2147483647)] | None = None

    @field_validator('model_number', 'model_name', 'device_type', 'firmware_version',
                     'description', 'department', 'department_code', 'location', 'status', mode='before')
    @classmethod
    def normalize_optional_text(cls, value, info):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            return None
        if info.field_name in ('device_type', 'status'):
            choices = DEVICE_TYPES if info.field_name == 'device_type' else STATUSES
            normalized = value.replace('_', ' ').casefold()
            return next((item for item in choices if item.casefold() == normalized), value)
        return value



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


    @computed_field
    @property
    def reference_remaining_life_years(self) -> Decimal | None:
        if self.expected_useful_life is None:
            return None
        remaining = Decimal(self.expected_useful_life) - exact_age(self.in_service_date, self.calculated_as_of)
        return two_places(max(Decimal(0), remaining))


class Prediction(BaseModel):
    model_version: str = "unreported"
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
    model_input_category: str | None = None
    reference_remaining_life_years: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    training_repair_rate_min: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    training_repair_rate_max: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None


class Assessment(BaseModel):
    equipment_id: UUID
    risk_score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, description='Relative repair-intensity percentile from 0 to 1; not failure probability.')]
    risk_level: Literal['low', 'medium', 'high']
    assessed_at: datetime
    method: str
    recommendation: str
    limitation: str
    prediction: Prediction


    @computed_field
    @property
    def repair_rate_percentile(self) -> float:
        # Keep risk_score for older clients; use the clearer name in new displays.
        return self.risk_score

class MaintenanceSchedules(BaseModel):
    asset_tag: Text50
    scheduled_start_time: datetime
    scheduled_end_time: datetime
    status: SCHEDULED_MAINTENANCE_STATUSES
    status_msg: str | None = None
    priority_score: int
