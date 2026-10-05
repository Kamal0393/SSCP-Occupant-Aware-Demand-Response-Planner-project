from pydantic import BaseModel, Field, model_validator

from app.api.schemas.appliance import ApplianceSchema
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
    energy_cost: float = Field(default=0.25, ge=0)


class EmergencyOverrideSchema(BaseModel):
    operator_id: str = Field(min_length=1, max_length=100)
    justification: str = Field(min_length=12, max_length=1000)


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
    appliances: tuple[ApplianceSchema, ...] = ()
    emergency_override: EmergencyOverrideSchema | None = None
    transformer_load_profile_kw: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def validate_references(self) -> "PlanningRequestSchema":
        if self.dr_event.transformer_id != self.transformer.id:
            raise ValueError("DR event transformer_id must match the supplied transformer")
        building_ids = {building.id for building in self.buildings}
        if any(building.transformer_id != self.transformer.id for building in self.buildings):
            raise ValueError("every building must belong to the supplied transformer")
        if any(occupant.building_id not in building_ids for occupant in self.occupants):
            raise ValueError("every occupant must reference a supplied building")
        if any(occupant.comfort_range_id not in self.comfort_ranges for occupant in self.occupants):
            raise ValueError("every occupant must reference a supplied comfort range")
        if any(appliance.building_id not in building_ids for appliance in self.appliances):
            raise ValueError("every appliance must reference a supplied building")
        if self.transformer_load_profile_kw is not None and not self.transformer_load_profile_kw:
            raise ValueError("transformer load profile cannot be empty")
        if self.transformer_load_profile_kw is not None and any(load < 0 for load in self.transformer_load_profile_kw):
            raise ValueError("transformer load profile values cannot be negative")
        return self


class PlanningResponseSchema(BaseModel):
    decisions: list[DecisionSchema]
    metrics: dict[str, float | int | bool | None] | None = None
    planning_result_id: str | None = None
