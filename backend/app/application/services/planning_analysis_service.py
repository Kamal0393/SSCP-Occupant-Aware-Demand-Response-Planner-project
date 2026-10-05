"""Derives plan metrics exclusively from its context and returned decisions."""

from dataclasses import asdict, dataclass
from math import ceil

from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import ActionType, Decision
from app.domain.constraints.soft_constraints import schedule_preference_penalty


@dataclass(frozen=True)
class PlanningMetrics:
    baseline_peak_load_kw: float
    optimized_peak_load_kw: float
    peak_reduction_kw: float
    peak_reduction_pct: float
    baseline_energy_kwh: float
    optimized_energy_kwh: float
    energy_difference_kwh: float
    estimated_cost_difference: float | None
    comfort_impact: float | None
    comfort_metric: float | None
    cost_metric: float | None
    comfort_weight: float
    cost_weight: float
    stakeholder_objective_value: float | None
    modified_decision_count: int
    protected_decision_count: int
    opted_out_decision_count: int
    infeasible: bool

    def to_dict(self) -> dict:
        return asdict(self)


class PlanningAnalysisService:
    def analyze(self, context: PlanningContext, decisions: list[Decision]) -> PlanningMetrics:
        slot_hours = 0.25
        start_slot = (context.dr_event.start_time.hour * 60 + context.dr_event.start_time.minute) // 15
        slot_count = max(1, ceil(context.dr_event.duration_minutes / 15))
        event_slots = tuple((start_slot + offset) % 96 for offset in range(slot_count))
        profile = context.transformer_load_profile

        if profile is not None:
            baseline_by_slot = {slot: profile.values_kw[slot % len(profile.values_kw)] for slot in event_slots}
        else:
            # Use measured load plus declared, non-running appliance schedules
            # to form the event baseline when a measured profile is absent.
            baseline_by_slot = {slot: context.transformer.current_load_kw for slot in event_slots}
            for appliance in context.appliances:
                if appliance.preferred_slot is None or appliance.is_running:
                    continue
                for offset in range(appliance.duration_slots):
                    scheduled_slot = (appliance.preferred_slot + offset) % 96
                    if scheduled_slot in baseline_by_slot:
                        baseline_by_slot[scheduled_slot] += appliance.rated_power_kw

        optimized_by_slot = dict(baseline_by_slot)
        appliances = {appliance.id: appliance for appliance in context.appliances}
        load_reductions = sum(
            max(0.0, decision.estimated_reduction_kw)
            for decision in decisions
            if decision.target_variable == "flexible_load_kw"
        )
        for slot in event_slots:
            optimized_by_slot[slot] = max(0.0, optimized_by_slot[slot] - load_reductions)

        for decision in decisions:
            appliance = appliances.get(decision.target_variable or "")
            if appliance is None or decision.before_value is None or decision.after_value is None:
                continue
            old_start, new_start = int(decision.before_value), int(decision.after_value)
            for offset in range(appliance.duration_slots):
                old_slot, new_slot = (old_start + offset) % 96, (new_start + offset) % 96
                if old_slot in optimized_by_slot:
                    optimized_by_slot[old_slot] = max(0.0, optimized_by_slot[old_slot] - appliance.rated_power_kw)
                if new_slot in optimized_by_slot:
                    optimized_by_slot[new_slot] += appliance.rated_power_kw

        baseline_peak = max(baseline_by_slot.values())
        optimized_peak = max(optimized_by_slot.values())
        peak_reduction = baseline_peak - optimized_peak
        baseline_energy = sum(baseline_by_slot.values()) * slot_hours
        optimized_energy = sum(optimized_by_slot.values()) * slot_hours
        baseline_cost = None
        if context.tariff is not None:
            baseline_cost = sum(
                baseline_by_slot[slot] * context.tariff.get_rate(slot) * slot_hours
                for slot in event_slots
            )

        cost_difference = None
        if context.tariff is not None:
            cost_difference = -sum(
                load_reductions * context.tariff.get_rate(slot) * slot_hours
                for slot in event_slots
            )
            # Appliance schedules preserve energy; account for the price
            # change across their original and selected slots.
            for decision in decisions:
                appliance = appliances.get(decision.target_variable or "")
                if appliance is None or decision.before_value is None or decision.after_value is None:
                    continue
                old_slot, new_slot = int(decision.before_value), int(decision.after_value)
                cost_difference += appliance.rated_power_kw * appliance.duration_slots * slot_hours * (
                    context.tariff.get_rate(new_slot) - context.tariff.get_rate(old_slot)
                )

        scores_by_occupant = {
            decision.occupant_id: decision.comfort_score
            for decision in decisions
            if decision.occupant_id is not None and decision.comfort_score is not None
        }
        comfort_impact = (sum(scores_by_occupant.values()) / len(scores_by_occupant) - 1.0
                          if scores_by_occupant else None)
        comfort_scores = list(scores_by_occupant.values())
        for decision in decisions:
            appliance = appliances.get(decision.target_variable or "")
            if appliance is None or decision.before_value is None or decision.after_value is None:
                continue
            comfort_scores.append(1.0 - schedule_preference_penalty(
                appliance.preferred_slot,
                int(decision.after_value),
                appliance.max_shift_slots,
            ))
        comfort_metric = (
            sum(comfort_scores) / len(comfort_scores) if comfort_scores else None
        )
        cost_metric = (
            cost_difference / baseline_cost
            if cost_difference is not None and baseline_cost is not None and baseline_cost > 0
            else None
        )
        comfort_weight = float(context.objective_weights.get("comfort", 0.5))
        cost_weight = float(context.objective_weights.get(
            "energy_cost", context.objective_weights.get("cost_weight", 0.25)
        ))
        stakeholder_objective_value = (
            comfort_weight * (1.0 - comfort_metric) + cost_weight * cost_metric
            if comfort_metric is not None and cost_metric is not None
            else None
        )
        protected = sum(
            decision.action == ActionType.OPT_OUT_RESPECTED
            or "COMFORT_PROTECTED" in decision.reasoning_tags
            or "WITHIN_HARD_COMFORT_BOUNDS" in decision.reasoning_tags
            for decision in decisions
        )
        opted_out = sum("OPTED_OUT" in decision.reasoning_tags for decision in decisions)
        modified = sum(
            decision.estimated_reduction_kw > 0
            or decision.action in (ActionType.DEFER_APPLIANCE, ActionType.OVERRIDE_APPLIED)
            for decision in decisions
        )
        infeasible = any("INFEASIBLE_REQUEST" in decision.reasoning_tags for decision in decisions)
        peak_pct = peak_reduction / baseline_peak * 100.0 if baseline_peak else 0.0

        return PlanningMetrics(
            baseline_peak_load_kw=baseline_peak,
            optimized_peak_load_kw=optimized_peak,
            peak_reduction_kw=peak_reduction,
            peak_reduction_pct=peak_pct,
            baseline_energy_kwh=baseline_energy,
            optimized_energy_kwh=optimized_energy,
            energy_difference_kwh=optimized_energy - baseline_energy,
            estimated_cost_difference=cost_difference,
            comfort_impact=comfort_impact,
            comfort_metric=comfort_metric,
            cost_metric=cost_metric,
            comfort_weight=comfort_weight,
            cost_weight=cost_weight,
            stakeholder_objective_value=stakeholder_objective_value,
            modified_decision_count=modified,
            protected_decision_count=protected,
            opted_out_decision_count=opted_out,
            infeasible=infeasible,
        )
