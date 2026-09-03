from app.domain.strategies.solver_interface import DemandResponseSolver
from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import ActionType, Decision


class OptimizedStrategy(DemandResponseStrategy):
    """Optimization-based demand-response strategy."""

    def __init__(self, solver: DemandResponseSolver) -> None:
        self._solver = solver

    @property
    def strategy_name(self) -> str:
        return "optimized"

    def generate_plan(self, context: PlanningContext) -> list[Decision]:
        flexible_loads = {
            str(building.id): building.flexible_load_kw
            for building in context.buildings
        }

        opted_out_building_ids = {
            occupant.building_id
            for occupant in context.occupants
            if occupant.opted_out
        }

        reductions = self._solver.solve(
            flexible_loads=flexible_loads,
            target_reduction_kw=context.dr_event.target_reduction_kw,
            opted_out_building_ids=opted_out_building_ids,
        )

        decisions: list[Decision] = []

        for building in context.buildings:
            building_id = str(building.id)
            reduction_kw = reductions.get(building_id, 0.0)
            after_load = building.flexible_load_kw - reduction_kw

            decisions.append(
                Decision(
                    id=f"{context.dr_event.id}-{building.id}",
                    dr_event_id=context.dr_event.id,
                    building_id=building_id,
                    slot_index=0,
                    action=(
                        ActionType.REDUCE_SETPOINT
                        if reduction_kw > 0
                        else ActionType.NO_ACTION
                    ),
                    triggering_constraint="optimized_peak_reduction",
                    objective_weights_used=dict(context.objective_weights),
                    target_variable=(
                        "flexible_load_kw"
                        if reduction_kw > 0
                        else None
                    ),
                    before_value=building.flexible_load_kw,
                    after_value=after_load,
                    reasoning_tags=(
                        (
                            "OPTIMIZED_STRATEGY",
                            "DR_EVENT_ACTIVE",
                            "FLEXIBLE_LOAD_REDUCED",
                        )
                        if reduction_kw > 0
                        else (
                            "OPTIMIZED_STRATEGY",
                            "NO_ACTION_REQUIRED",
                        )
                    ),
                    estimated_reduction_kw=reduction_kw,
                )
            )

        return decisions