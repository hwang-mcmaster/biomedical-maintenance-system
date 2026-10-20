from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class EquipmentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: RequiredText
    type: RequiredText
    location: RequiredText
    status: Literal['Operational', 'Under Maintenance', 'Inactive']


class Equipment(EquipmentCreate):
    id: int
