from app.domain.value_objects.decision import ActionType, Decision


class ExplanationService:
    """Builds human-readable explanations for planning decisions."""

    def explain(self, decision: Decision) -> str:
        if decision.action == ActionType.NO_ACTION:
            return (
                f"Building {decision.building_id}: no action was taken."
            )

        if decision.action == ActionType.OPT_OUT_RESPECTED:
            explanation = (
                f"Building {decision.building_id}: "
                "occupant opt-out was respected."
            )

            if decision.reasoning_tags:
                tags = ", ".join(decision.reasoning_tags)
                explanation += f" Reasoning tags: {tags}."

            return explanation

        explanation = (
            f"Building {decision.building_id}: "
            f"reduced load by {decision.estimated_reduction_kw:.1f} kW "
            f"because of {decision.triggering_constraint}."
        )

        if decision.reasoning_tags:
            tags = ", ".join(decision.reasoning_tags)
            explanation += f" Reasoning tags: {tags}."

        if decision.is_override:
            explanation += " An authorized override was applied."

        if decision.objective_weights_used:
            weights = ", ".join(
                f"{name}={weight}"
                for name, weight in decision.objective_weights_used.items()
            )
            explanation += f" Objective weights: {weights}."

        return explanation