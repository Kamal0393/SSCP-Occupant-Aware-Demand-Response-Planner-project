from app.domain.value_objects.decision import ActionType, Decision


class ExplanationService:
    """Deterministic explanations derived from decision reason codes and values."""

    def explain(self, decision: Decision) -> str:
        tags = set(decision.reasoning_tags)
        if "INFEASIBLE_REQUEST" in tags:
            return (
                f"Building {decision.building_id}: the requested reduction is infeasible; "
                "available flexible load cannot satisfy transformer protection and opt-out constraints. "
                f"Solver status: {self._tag_value(tags, 'SOLVER_STATUS:') or 'infeasible'}."
            )

        if decision.action == ActionType.OPT_OUT_RESPECTED:
            return (f"Building {decision.building_id}: no load was changed because the occupant opt-out was respected."
                    + self._tag_sentence(decision))

        if decision.action == ActionType.DEFER_APPLIANCE:
            explanation = (
                f"Building {decision.building_id}: flexible appliance {decision.target_variable} "
                f"was moved from slot {int(decision.before_value or 0)} to slot {int(decision.after_value or 0)}."
            )
            if "TARIFF_BASED_SHIFT" in tags:
                explanation += " The new slot has a lower tariff rate."
            elif "TARIFF_COST_TRADEOFF" in tags:
                explanation += " The schedule balances transformer relief against tariff cost."
            if "TRANSFORMER_PEAK_PROTECTION" in tags:
                explanation += " Moving it clears load from the demand-response event window."
            return explanation + self._tag_sentence(decision)

        if decision.is_override or decision.action == ActionType.OVERRIDE_APPLIED:
            operator = self._tag_value(tags, "OVERRIDE_OPERATOR:")
            justification = self._tag_value(tags, "OVERRIDE_JUSTIFICATION:")
            details = f" Operator: {operator}." if operator else ""
            if justification:
                details += f" Justification: {justification}."
            return (
                f"Building {decision.building_id}: an explicitly authorized emergency action reduced "
                f"flexible load by {decision.estimated_reduction_kw:.1f} kW for transformer protection."
                f"{details} The occupant had opted in to emergency override, and comfort hard bounds remain enforced."
            ) + self._tag_sentence(decision)

        if decision.action == ActionType.NO_ACTION:
            if "COMFORT_PROTECTED" in tags:
                return f"Building {decision.building_id}: no load was changed to preserve the occupant's comfort preference."
            if "NO_ACTIVE_FLEXIBLE_APPLIANCE" in tags:
                return f"Building {decision.building_id}: no action was possible because it has no running flexible appliance."
            if "COMFORT_PRESERVED" in tags:
                return f"Building {decision.building_id}: no action was needed; the plan preserved the occupant's comfort preference."
            return f"Building {decision.building_id}: no action was needed for the requested peak reduction." + self._tag_sentence(decision)

        if decision.triggering_constraint == "transformer_capacity_protection":
            reason = "to bring transformer demand below its rated capacity"
        elif decision.triggering_constraint == "high_tariff_peak_reduction":
            reason = "during a high-tariff period, reducing both the peak and estimated energy cost"
        elif decision.triggering_constraint == "comfort_preference_tradeoff":
            reason = "while balancing peak reduction against occupant comfort"
        else:
            reason = (f"because of {decision.triggering_constraint.replace('_', ' ')} "
                      f"({decision.triggering_constraint})")

        explanation = (
            f"Building {decision.building_id}: reduced flexible load by "
            f"{decision.estimated_reduction_kw:.1f} kW {reason}."
        )
        if decision.comfort_score is not None:
            explanation += f" Estimated comfort score after the action is {decision.comfort_score:.2f} (0 to 1)."
        if "APPLIANCE_FLEXIBILITY" in tags:
            explanation += " Only currently running flexible appliances were eligible for reduction."
        if "WITHIN_HARD_COMFORT_BOUNDS" in tags:
            explanation += " The action remains within the occupant's hard comfort bounds."
        if decision.objective_weights_used:
            weights = ", ".join(f"{key}={value:g}" for key, value in sorted(decision.objective_weights_used.items()))
            explanation += f" Objective weights: {weights}."
        return explanation + self._tag_sentence(decision)

    @staticmethod
    def _tag_sentence(decision: Decision) -> str:
        return f" Reasoning tags: {', '.join(decision.reasoning_tags)}." if decision.reasoning_tags else ""

    @staticmethod
    def _tag_value(tags: set[str], prefix: str) -> str | None:
        return next((tag[len(prefix):] for tag in tags if tag.startswith(prefix)), None)
