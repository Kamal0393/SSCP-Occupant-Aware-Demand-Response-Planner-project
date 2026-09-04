from pydantic import BaseModel, Field


class TransformerSchema(BaseModel):
    id: str
    name: str
    rated_capacity_kw: float = Field(gt=0)
    current_load_kw: float = Field(ge=0)
    connected_building_ids: tuple[str, ...] = ()
    safety_margin_pct: float = Field(default=0.10, ge=0, lt=1)