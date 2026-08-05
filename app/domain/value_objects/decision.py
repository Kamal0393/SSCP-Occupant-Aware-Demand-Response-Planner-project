"""
Module: decision.py

Purpose:
    Defines Decision, the single most important contract in this system. Every
    action a strategy (baseline or optimized) proposes is represented as a
    Decision. The explanation service consumes Decisions to produce
    plain-English text; the API serializes Decisions directly to the frontend;
    experiments aggregate Decisions to compute peak reduction, comfort score,
    and override counts.

Design decisions:
    - Decision is intentionally "dumb data" - it carries no behaviour beyond
      simple derived properties. All reasoning happens in the strategies that
      construct it. This means the explanation engine can be unit tested with
      hand-built Decision objects with no solver dependency at all.
    - `triggering_constraint` and `reasoning_tags` are separated: the former
      is the specific constraint (hard or soft) that most directly justified
      the action, while the latter is a small set of machine-readable tags
      (e.g. "UNOCCUPIED", "OVERLOAD_ACTIVE", "WITHIN_COMFORT_RANGE") that the
      template engine composes into the final sentence. This keeps the
      explanation *generation* logic swappable (template today, LLM-based
      later) without touching the optimizer.
    - `objective_weights_used` records exactly which weighting was active
      when this decision was made (e.g. {"peak_reduction": 0.7, "comfort":
      0.3}), which is essential for the "compare at least two competing
      objectives" requirement to be demonstrable and auditable after the run,
      not just described in a demo narrative.
"""

from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    ADJUST_TEMPERATURE = "adjust_temperature"
    DEFER_APPLIANCE = "defer_appliance"
    REDUCE_SETPOINT = "reduce_setpoint"
    NO_ACTION = "no_action"
    OPT_OUT_RESPECTED = "opt_out_respected"
    OVERRIDE_APPLIED = "override_applied"


@dataclass(frozen=True)
class Decision:
    """
    A single proposed (or applied) action against one building/occupant,
    within the context of one DR event and one time slot.

    Attributes:
        id: Unique decision identifier.
        dr_event_id: The event this decision was generated for.
        building_id: Target building.
        occupant_id: Target occupant, if the action is occupant-scoped.
        slot_index: Which discrete time slot this decision applies to.
        action: The type of action taken.
        target_variable: Name of the variable changed (e.g. "temperature_c"),
            or None for NO_ACTION / OPT_OUT_RESPECTED.
        before_value: Value prior to this decision.
        after_value: Value after this decision.
        triggering_constraint: Human-readable id/name of the constraint that
            most directly justified this decision (e.g.
            "transformer_overload_hard_limit", "comfort_soft_preference").
        objective_weights_used: The objective weighting active when this
            decision was produced, e.g. {"peak_reduction": 0.7, "comfort": 0.3}.
        reasoning_tags: Machine-readable tags consumed by the explanation
            template engine to build the plain-English sentence.
        is_override: True if this decision required an authorized operator
            override to bypass an occupant's opt-out or a soft constraint.
        estimated_reduction_kw: Estimated contribution to peak reduction for
            this decision (0 for NO_ACTION).
        comfort_score: The occupant comfort score in [0, 1] AFTER this
            decision is applied, computed from the relevant ComfortRange.
    """

    id: str
    dr_event_id: str
    building_id: str
    slot_index: int
    action: ActionType
    triggering_constraint: str
    objective_weights_used: dict[str, float]
    occupant_id: str | None = None
    target_variable: str | None = None
    before_value: float | None = None
    after_value: float | None = None
    reasoning_tags: tuple[str, ...] = field(default_factory=tuple)
    is_override: bool = False
    estimated_reduction_kw: float = 0.0
    comfort_score: float | None = None

    @property
    def delta(self) -> float | None:
        if self.before_value is None or self.after_value is None:
            return None
        return self.after_value - self.before_value
