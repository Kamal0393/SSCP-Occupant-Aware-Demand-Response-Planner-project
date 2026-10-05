"""Derives plan metrics exclusively from its context and returned decisions."""

from dataclasses import asdict, dataclass
from math import ceil

from app.core.exceptions import MissingTariffDataError
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import ActionType, Decision


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

        cost_difference = None
        if context.tariff is not None:
            try:
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
            except MissingTariffDataError:
                cost_difference = None

        scores_by_occupant = {
            decision.occupant_id: decision.comfort_score
            for decision in decisions
            if decision.occupant_id is not None and decision.comfort_score is not None
        }
        comfort_impact = (sum(scores_by_occupant.values()) / len(scores_by_occupant) - 1.0
                          if scores_by_occupant else None)
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
            modified_decision_count=modified,
            protected_decision_count=protected,
            opted_out_decision_count=opted_out,
            infeasible=infeasible,
        )
