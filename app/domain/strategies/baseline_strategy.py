from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import ActionType, Decision


class BaselineStrategy(DemandResponseStrategy):
    """
    Simple deterministic demand-response baseline.

    The baseline does not optimize comfort, tariffs, or occupant preferences.
    It reduces flexible building load in deterministic building-id order
    until the requested reduction is satisfied.
    """

    @property
    def strategy_name(self) -> str:
        return "baseline"

    def generate_plan(self, context: PlanningContext) -> list[Decision]:
        decisions: list[Decision] = []

        required_reduction = context.dr_event.target_reduction_kw

        # The baseline cannot reduce more flexible load than is available.
        available_flexible_load = sum(
            building.flexible_load_kw
            for building in context.buildings
        )

        reduction_remaining = min(
            required_reduction,
            available_flexible_load,
        )

        for building in sorted(context.buildings, key=lambda item: item.id):
            if reduction_remaining <= 0:
                decisions.append(
                    self._no_action_decision(context, building.id)
                )
                continue

            reducible_kw = min(
                building.flexible_load_kw,
                reduction_remaining,
            )

            if reducible_kw <= 0:
                decisions.append(
                    self._no_action_decision(context, building.id)
                )
                continue

            after_load = building.flexible_load_kw - reducible_kw

            decisions.append(
                Decision(
                    id=f"{context.dr_event.id}-{building.id}",
                    dr_event_id=context.dr_event.id,
                    building_id=building.id,
                    slot_index=0,
                    action=ActionType.REDUCE_SETPOINT,
                    triggering_constraint="dr_event_target_reduction",
                    objective_weights_used=dict(context.objective_weights),
                    target_variable="flexible_load_kw",
                    before_value=building.flexible_load_kw,
                    after_value=after_load,
                    reasoning_tags=(
                        "BASELINE_STRATEGY",
                        "DR_EVENT_ACTIVE",
                        "FLEXIBLE_LOAD_REDUCED",
                    ),
                    estimated_reduction_kw=reducible_kw,
                )
            )

            reduction_remaining -= reducible_kw

        return decisions

    @staticmethod
    def _no_action_decision(
        context: PlanningContext,
        building_id: str,
    ) -> Decision:
        return Decision(
            id=f"{context.dr_event.id}-{building_id}",
            dr_event_id=context.dr_event.id,
            building_id=building_id,
            slot_index=0,
            action=ActionType.NO_ACTION,
            triggering_constraint="no_reduction_required",
            objective_weights_used=dict(context.objective_weights),
            reasoning_tags=("BASELINE_STRATEGY", "NO_ACTION_REQUIRED"),
            estimated_reduction_kw=0.0,
        )
    