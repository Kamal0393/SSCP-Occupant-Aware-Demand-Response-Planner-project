from ortools.sat.python import cp_model

from app.domain.entities import occupant
from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import ActionType, Decision


class OptimizedStrategy(DemandResponseStrategy):
    """OR-Tools based demand-response optimization strategy."""

    @property
    def strategy_name(self) -> str:
        return "optimized"

    def generate_plan(self, context: PlanningContext) -> list[Decision]:
        model = cp_model.CpModel()

        scale = 100

        reduction_vars = {}

        for building in context.buildings:
            max_reduction = int(round(building.flexible_load_kw * scale))

            occupant = next(
                (
                    occupant
                    for occupant in context.occupants
                    if occupant.building_id == str(building.id)
                ),
                None,
            )

            if occupant is not None and occupant.opted_out:
                max_reduction = 0

            reduction_vars[building.id] = model.new_int_var(
                0,
                max_reduction,
                f"reduction_{building.id}",
            )
        target_reduction = int(
            round(context.dr_event.target_reduction_kw * scale)
        )

        model.add(
            sum(reduction_vars.values()) <= target_reduction
        )
        model.maximize(
            sum(reduction_vars.values())
        )
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        if status not in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        ):
            return []
        decisions: list[Decision] = []

        for building in context.buildings:
            reduction_kw = solver.value(reduction_vars[building.id]) / scale
            after_load = building.flexible_load_kw - reduction_kw

            decisions.append(
                Decision(
                    id=f"{context.dr_event.id}-{building.id}",
                    dr_event_id=context.dr_event.id,
                    building_id=building.id,
                    slot_index=0,
                    action=ActionType.REDUCE_SETPOINT
                    if reduction_kw > 0
                    else ActionType.NO_ACTION,
                    triggering_constraint="optimized_peak_reduction",
                    objective_weights_used=dict(context.objective_weights),
                    target_variable="flexible_load_kw"
                    if reduction_kw > 0
                    else None,
                    before_value=building.flexible_load_kw,
                    after_value=after_load,
                    reasoning_tags=(
                        "OPTIMIZED_STRATEGY",
                        "DR_EVENT_ACTIVE",
                        "FLEXIBLE_LOAD_REDUCED",
                    )
                    if reduction_kw > 0
                    else (
                        "OPTIMIZED_STRATEGY",
                        "NO_ACTION_REQUIRED",
                    ),
                    estimated_reduction_kw=reduction_kw,
                )
            )

        return decisions