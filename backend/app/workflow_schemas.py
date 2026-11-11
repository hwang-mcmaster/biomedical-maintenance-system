from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import Field, model_validator
from .scheduling_schemas import InputModel, Label, Priority, TimeWindow
from .calculations import reference_date

class Availability(TimeWindow):
    date: date

class TechnicianInput(InputModel):
    name: Label
    qualifications: Annotated[list[Label], Field(min_length=1, max_length=20)]
    availability: Annotated[list[Availability], Field(max_length=100)] = Field(default_factory=list)

    @model_validator(mode='after')
    def no_overlaps(self):
        windows = sorted(self.availability, key=lambda w: (w.date, w.start))
        if any(a.date == b.date and a.end > b.start for a,b in zip(windows, windows[1:])):
            raise ValueError('Technician availability windows must not overlap.')
        if any(w.date < reference_date() for w in windows):
            raise ValueError('Availability cannot start before today in Toronto.')
        return self

class TaskInput(InputModel):
    request_id: UUID = Field(default_factory=uuid4)
    equipment_id: UUID
    title: Annotated[str, Field(min_length=1, max_length=150)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)]
    required_qualification: Label
    use_assessment: bool = True
    priority_override: Priority | None = None
    override_reason: Annotated[str, Field(min_length=3, max_length=2000)] | None = None
    due_date: date | None = None

    @model_validator(mode='after')
    def explicit_priority(self):
        self.title=self.title.strip()
        if not self.title: raise ValueError('Task title is required.')
        if self.override_reason is not None: self.override_reason=self.override_reason.strip()
        if self.override_reason is not None and len(self.override_reason)<3: raise ValueError('Priority explanation must contain at least three non-space characters.')
        if self.priority_override and not self.override_reason: raise ValueError('A priority override requires an explanation.')
        if not self.use_assessment and not (self.priority_override and self.override_reason):
            raise ValueError('Without assessment, enter an explicit priority and explanation.')
        if self.due_date and self.due_date < reference_date(): raise ValueError('Target date cannot be in the past.')
        return self

class PlanInput(InputModel):
    schedule_date: date
    task_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]

    @model_validator(mode='after')
    def valid(self):
        if self.schedule_date < reference_date(): raise ValueError('Schedule date cannot be in the past.')
        if len(set(self.task_ids)) != len(self.task_ids): raise ValueError('Task IDs must be unique.')
        return self

class StatusInput(InputModel):
    status: Literal['in_progress','completed','cancelled']
    notes: Annotated[str, Field(min_length=3, max_length=2000)]
    actual_cost: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] = Decimal('0.00')

    @model_validator(mode='after')
    def nonblank(self):
        self.notes=self.notes.strip()
        if len(self.notes)<3: raise ValueError('Provide a meaningful status note.')
        return self
