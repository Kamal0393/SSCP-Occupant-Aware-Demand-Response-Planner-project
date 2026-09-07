from pydantic import BaseModel

from app.domain.value_objects.decision import ActionType


class DecisionSchema(BaseModel):
    id: str
    dr_event_id: str
    building_id: str
    occupant_id: str | None = None
    slot_index: int
    action: ActionType
    target_variable: str | None = None
    before_value: float | None = None
    after_value: float | None = None
    triggering_constraint: str
    objective_weights_used: dict[str, float]
    reasoning_tags: tuple[str, ...] = ()
    is_override: bool = False
    estimated_reduction_kw: float = 0.0
    comfort_score: float | None = None
    delta: float | None = None
    