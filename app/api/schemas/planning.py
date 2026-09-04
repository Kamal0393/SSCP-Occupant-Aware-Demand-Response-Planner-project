from pydantic import BaseModel, Field

from app.api.schemas.building import BuildingSchema
from app.api.schemas.comfort_range import ComfortRangeSchema
from app.api.schemas.decision import DecisionSchema
from app.api.schemas.dr_event import DREventSchema
from app.api.schemas.occupant import OccupantSchema
from app.api.schemas.tariff import TariffSchema
from app.api.schemas.transformer import TransformerSchema


class ObjectiveWeightsSchema(BaseModel):
    peak_reduction: float = Field(ge=0)
    comfort: float = Field(ge=0)


class PlanningRequestSchema(BaseModel):
    dr_event: DREventSchema
    transformer: TransformerSchema
    buildings: tuple[BuildingSchema, ...]
    occupants: tuple[OccupantSchema, ...]
    comfort_ranges: dict[str, ComfortRangeSchema]
    tariff: TariffSchema | None = None
    objective_weights: ObjectiveWeightsSchema = ObjectiveWeightsSchema(
        peak_reduction=0.5,
        comfort=0.5,
    )


class PlanningResponseSchema(BaseModel):
    decisions: list[DecisionSchema]
    