from pydantic import BaseModel, Field

from app.domain.entities.appliance import ApplianceType


class ApplianceSchema(BaseModel):
    id: str
    building_id: str
    name: str
    appliance_type: ApplianceType
    rated_power_kw: float = Field(gt=0)
    is_flexible: bool = False
    is_running: bool = False
    preferred_slot: int | None = Field(default=None, ge=0, lt=96)
    max_shift_slots: int = Field(default=0, ge=0, le=96)
    duration_slots: int = Field(default=1, gt=0, le=96)
