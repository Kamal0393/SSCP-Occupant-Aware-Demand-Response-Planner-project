from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domain.entities.dr_event import DREventStatus


class DREventSchema(BaseModel):
    id: str
    transformer_id: str
    start_time: datetime
    end_time: datetime
    target_reduction_kw: float = Field(gt=0)
    status: DREventStatus = DREventStatus.PLANNED

    @model_validator(mode="after")
    def validate_times(self) -> "DREventSchema":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self