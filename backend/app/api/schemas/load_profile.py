from pydantic import BaseModel, Field


class LoadProfileSchema(BaseModel):
    entity_id: str
    values_kw: tuple[float, ...] = Field(min_length=1, max_length=96)
