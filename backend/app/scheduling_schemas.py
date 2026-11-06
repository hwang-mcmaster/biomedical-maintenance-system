"""Single-day scheduling inputs. Availability is explicitly supplied, not inferred."""
from datetime import date, datetime, time
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from .calculations import reference_date

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Priority = Literal['High', 'Medium', 'Low']


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TimeWindow(InputModel):
    start: time
    end: time

    @field_validator('start', 'end')
    @classmethod
    def minute_local_time(cls, value):
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError('Use local Toronto time in HH:MM, without seconds or an offset.')
        return value

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start:
            raise ValueError('End must be after start within the same day.')
        return self


class Technician(InputModel):
    id: Identifier
    name: Label
    qualifications: Annotated[list[Label], Field(min_length=1, max_length=20)]
    availability: Annotated[list[TimeWindow], Field(max_length=10)]

    @model_validator(mode='after')
    def nonoverlapping_availability(self):
        ordered = sorted(self.availability, key=lambda window: window.start)
        if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Availability windows for one technician must not overlap.')
        return self


class MaintenanceTask(InputModel):
    id: Identifier
    equipment_id: UUID
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    priority: Priority = 'Medium'
    required_qualification: Label
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)]


class ExistingBooking(TimeWindow):
    id: Identifier
    technician_id: Identifier
    equipment_id: UUID


class ScheduleRequest(InputModel):
    schedule_date: date
    tasks: Annotated[list[MaintenanceTask], Field(min_length=1, max_length=100)]
    technicians: Annotated[list[Technician], Field(min_length=1, max_length=30)]
    existing_bookings: Annotated[list[ExistingBooking], Field(max_length=200)] = Field(default_factory=list)

    @field_validator('schedule_date')
    @classmethod
    def not_past(cls, value):
        if value < reference_date():
            raise ValueError('Schedule date cannot be before today in Toronto.')
        return value

    @model_validator(mode='after')
    def unique_ids_and_booking_references(self):
        for label, records in [('task', self.tasks), ('technician', self.technicians), ('booking', self.existing_bookings)]:
            ids = [record.id for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f'Each {label} ID must be unique.')
        technician_ids = {technician.id for technician in self.technicians}
        if any(booking.technician_id not in technician_ids for booking in self.existing_bookings):
            raise ValueError('Every booking must reference a supplied technician ID.')
        return self


class Assignment(BaseModel):
    task_id: str
    title: str
    equipment_id: UUID
    asset_tag: str
    technician_id: str
    technician_name: str
    priority: Priority
    required_qualification: str
    duration_minutes: int
    start: datetime
    end: datetime


class UnscheduledTask(BaseModel):
    task_id: str
    title: str
    equipment_id: UUID
    asset_tag: str
    priority: Priority
    reason_code: Literal['NO_QUALIFIED_TECHNICIAN', 'INSUFFICIENT_AVAILABILITY', 'RESOURCE_CONFLICT']
    reason: str


class SchedulePreview(BaseModel):
    schedule_date: date
    timezone: str = 'America/Toronto'
    algorithm: str = 'Priority first, then earliest feasible slot; ties use technician ID and task ID.'
    persisted: bool = False
    generated_at: datetime
    assignments: list[Assignment]
    unscheduled: list[UnscheduledTask]
    notices: list[str]
