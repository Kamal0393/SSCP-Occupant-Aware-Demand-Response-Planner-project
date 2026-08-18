from app.domain.value_objects.decision import ActionType, Decision


class ExplanationService:
    """Builds human-readable explanations for planning decisions."""

    def explain(self, decision: Decision) -> str:
        if decision.action == ActionType.NO_ACTION:
            return (
                f"Building {decision.building_id}: no action was taken."
            )

        return (
            f"Building {decision.building_id}: "
            f"reduced load by {decision.estimated_reduction_kw:.1f} kW "
            f"because of {decision.triggering_constraint}."
        )
        