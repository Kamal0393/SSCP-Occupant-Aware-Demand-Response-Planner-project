from pydantic import BaseModel, Field

from app.domain.entities.building import BuildingType


class BuildingSchema(BaseModel):
    id: str
    name: str
    transformer_id: str
    building_type: BuildingType
    floor_area_sqm: float = Field(gt=0)
    fixed_load_kw: float = Field(ge=0)
    flexible_load_kw: float = Field(ge=0)
    occupant_ids: tuple[str, ...] = ()
    