from app.core.exceptions import UnauthorizedOverrideError
from app.domain.constraints.hard_constraints import (
    enforce_comfort_hard_bounds,
    enforce_no_negative_load,
    enforce_opt_out,
)
from app.domain.constraints.soft_constraints import comfort_preference_penalty
from app.domain.entities.dr_event import DREventStatus
from math import ceil

from app.domain.strategies.solver_interface import (
    DemandResponseSolver,
    OptimizationProblem,
    SchedulableAppliance,
)
from app.domain.strategies.strategy_interface import DemandResponseStrategy, PlanningContext
from app.domain.value_objects.decision import ActionType, Decision


def _number_or(value, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) else fallback


class OptimizedStrategy(DemandResponseStrategy):
    """Constraint-aware demand-response planning over controllable building load."""

    def __init__(self, solver: DemandResponseSolver) -> None:
        self._solver = solver

    @property
    def strategy_name(self) -> str:
        return "optimized"

    def generate_plan(self, context: PlanningContext) -> list[Decision]:
        occupants_by_building: dict[str, list] = {}
        for occupant in context.occupants:
            occupants_by_building.setdefault(str(occupant.building_id), []).append(occupant)
        appliances_by_building: dict[str, list] = {}
        for appliance in context.appliances:
            appliances_by_building.setdefault(str(appliance.building_id), []).append(appliance)

        flexible_loads: dict[str, float] = {}
        maximum_reductions: dict[str, float] = {}
        comfort_sensitive_loads: dict[str, float] = {}
        maximum_comfort_reductions: dict[str, float] = {}
        comfort_penalties: dict[str, float] = {}
        opted_out_ids: set[str] = set()
        override_ids: set[str] = set()
        comfort_caps: dict[str, float] = {}

        for building in context.buildings:
            building_id = str(building.id)
            occupants = occupants_by_building.get(building_id, [])
            opted_out = [occupant for occupant in occupants if occupant.opted_out]
            has_override_consent = bool(opted_out) and all(o.allow_override for o in opted_out)
            authorized_override = context.emergency_override is not None and has_override_consent
            if opted_out and not authorized_override:
                opted_out_ids.add(building_id)
            elif authorized_override:
                override_ids.add(building_id)

            appliances = appliances_by_building.get(building_id)
            if appliances:
                active_flexible_kw = sum(
                    appliance.rated_power_kw
                    for appliance in appliances
                    if appliance.is_flexible and appliance.is_running
                )
                available_kw = min(building.flexible_load_kw, active_flexible_kw)
                sensitive_kw = min(available_kw, sum(
                    appliance.rated_power_kw for appliance in appliances
                    if appliance.is_flexible and appliance.is_running
                    and appliance.appliance_type.value == "hvac"
                ))
            else:
                # Backwards-compatible aggregate input when no appliance records are supplied.
                available_kw = building.flexible_load_kw
                sensitive_kw = available_kw
            flexible_loads[building_id] = available_kw
            comfort_sensitive_loads[building_id] = sensitive_kw

            comfort_ranges = [
                context.comfort_ranges[o.comfort_range_id]
                for o in occupants
                if o.comfort_range_id in context.comfort_ranges
            ]
            if comfort_ranges and sensitive_kw > 0:
                # Map HVAC curtailment proportionally to setpoint movement from
                # preferred temperature toward the upper hard comfort bound.
                # The cap keeps the proxy setpoint inside every occupant's range.
                sensitivity = max(0.0, context.hvac_setpoint_change_c_per_kw)
                headrooms = [comfort.max_value - comfort.preferred_value for comfort in comfort_ranges]
                comfort_cap = (min(sensitive_kw, min(headrooms) / sensitivity)
                               if sensitivity > 0 and min(headrooms) > 0 else 0.0)
                maximum_reductions[building_id] = available_kw
                maximum_comfort_reductions[building_id] = comfort_cap
                comfort_caps[building_id] = comfort_cap
                comfort_penalties[building_id] = (
                    max(sensitivity / headroom for headroom in headrooms)
                    if sensitivity > 0 and min(headrooms) > 0 else 0.0
                )
            else:
                maximum_reductions[building_id] = available_kw
                maximum_comfort_reductions[building_id] = 0.0
                comfort_sensitive_loads[building_id] = 0.0

        current_load = _number_or(getattr(context.transformer, "current_load_kw", 0.0), 0.0)
        rated_capacity = _number_or(getattr(context.transformer, "rated_capacity_kw", float("inf")), float("inf"))
        start_time = getattr(context.dr_event, "start_time", None)
        event_slot = ((start_time.hour * 60 + start_time.minute) // 15
                      if hasattr(start_time, "hour") and isinstance(start_time.hour, int) else 0)
        duration_minutes = _number_or(getattr(context.dr_event, "duration_minutes", 0.0), 0.0)
        event_slot_count = max(1, ceil(duration_minutes / 15)) if duration_minutes else 1
        event_slots = tuple((event_slot + offset) % 96 for offset in range(event_slot_count))
        event_peak = current_load
        if context.transformer_load_profile is not None:
            values = context.transformer_load_profile.values_kw
            event_peak = max(values[slot % len(values)] for slot in event_slots)
        capacity_reduction = max(0.0, event_peak - rated_capacity)
        if (context.emergency_override is not None
                and (event_peak <= rated_capacity or context.dr_event.status != DREventStatus.ACTIVE)):
            raise UnauthorizedOverrideError(
                "Emergency override requires an active event and an overloaded transformer"
            )
        schedulable = []
        for appliance in context.appliances:
            if (not appliance.is_flexible or appliance.is_running
                    or appliance.preferred_slot is None or appliance.max_shift_slots <= 0
                    or (str(appliance.building_id) in opted_out_ids
                        and str(appliance.building_id) not in override_ids)):
                continue
            candidates = tuple(
                slot for slot in range(max(0, appliance.preferred_slot - appliance.max_shift_slots),
                                       min(96 - appliance.duration_slots, appliance.preferred_slot + appliance.max_shift_slots) + 1)
                if appliance.preferred_slot in event_slots or slot not in event_slots
            )
            if candidates:
                schedulable.append(SchedulableAppliance(
                    appliance.id, str(appliance.building_id), appliance.rated_power_kw,
                    appliance.preferred_slot, appliance.duration_slots, candidates,
                ))
        outcome = self._solver.solve_problem(OptimizationProblem(
            flexible_loads=flexible_loads,
            target_reduction_kw=context.dr_event.target_reduction_kw,
            opted_out_building_ids=opted_out_ids,
            capacity_reduction_kw=capacity_reduction,
            override_building_ids=override_ids,
            maximum_reductions_kw=maximum_reductions,
            comfort_sensitive_loads_kw=comfort_sensitive_loads,
            maximum_comfort_sensitive_reductions_kw=maximum_comfort_reductions,
            comfort_penalty_per_kw=comfort_penalties,
            objective_weights=dict(context.objective_weights),
            tariff_rates=dict(context.tariff.rate_per_slot) if context.tariff else {},
            schedulable_appliances=tuple(schedulable),
            event_slots=event_slots,
        ))

        if not outcome.feasible:
            decisions = [
                self._opt_out_decision(context, building.id)
                if str(building.id) in opted_out_ids
                else self._infeasible_decision(context, building.id, outcome.status)
                for building in context.buildings
            ]
            if not any("INFEASIBLE_REQUEST" in d.reasoning_tags for d in decisions):
                decisions.append(self._infeasible_decision(
                    context, context.transformer.id, outcome.status
                ))
            return decisions

        bounded_reductions = {
            building_id: (0.0 if building_id in opted_out_ids else min(
                max(0.0, outcome.reductions_kw.get(building_id, 0.0)),
                maximum_reductions.get(building_id, 0.0),
            ))
            for building_id in flexible_loads
        }
        schedulable_by_id = {appliance.id: appliance for appliance in context.appliances}
        shifted_capacity_relief = sum(
            appliance.rated_power_kw
            for appliance_id, new_slot in outcome.appliance_slots.items()
            if (appliance := schedulable_by_id.get(appliance_id)) is not None
            and appliance.preferred_slot in event_slots and new_slot not in event_slots
        )
        if sum(bounded_reductions.values()) + shifted_capacity_relief + 1e-6 < capacity_reduction:
            decisions = [
                self._opt_out_decision(context, building.id)
                if str(building.id) in opted_out_ids
                else self._infeasible_decision(context, building.id, "post_validation_capacity_shortfall")
                for building in context.buildings
            ]
            if not any("INFEASIBLE_REQUEST" in decision.reasoning_tags for decision in decisions):
                decisions.append(self._infeasible_decision(
                    context, context.transformer.id, "post_validation_capacity_shortfall"
                ))
            return decisions

        decisions: list[Decision] = []
        tariff_rate = None
        if context.tariff is not None:
            tariff_rate = context.tariff.rate_per_slot.get(event_slot % 96)
        rate_mean = (sum(context.tariff.rate_per_slot.values()) / len(context.tariff.rate_per_slot)
                     if context.tariff and context.tariff.rate_per_slot else None)

        for building in context.buildings:
            building_id = str(building.id)
            occupants = occupants_by_building.get(building_id, [])
            reduction_kw = bounded_reductions.get(building_id, 0.0)
            if building_id in opted_out_ids:
                enforce_opt_out(next(o for o in occupants if o.opted_out), reduction_kw > 0)
                decisions.append(self._opt_out_decision(context, building.id))
                continue

            after_load = building.flexible_load_kw - reduction_kw
            enforce_no_negative_load(building_id, after_load)
            comfort_score = None
            if building_id in comfort_caps:
                score_by_occupant = []
                for occupant in occupants:
                    comfort = context.comfort_ranges.get(occupant.comfort_range_id)
                    if comfort is None:
                        continue
                    proposed_setpoint = comfort.preferred_value
                    sensitive_reduction = outcome.comfort_sensitive_reductions_kw.get(
                        building_id, min(reduction_kw, maximum_comfort_reductions.get(building_id, 0.0))
                    )
                    proposed_setpoint += sensitive_reduction * context.hvac_setpoint_change_c_per_kw
                    enforce_comfort_hard_bounds(comfort, proposed_setpoint)
                    # Invoke the same pure preference penalty used by domain constraints.
                    penalty = comfort_preference_penalty(comfort, proposed_setpoint)
                    score_by_occupant.append(1.0 - penalty)
                comfort_score = sum(score_by_occupant) / len(score_by_occupant) if score_by_occupant else None

            if reduction_kw > 0:
                is_override = building_id in override_ids
                action = ActionType.OVERRIDE_APPLIED if is_override else ActionType.REDUCE_SETPOINT
                overloaded = capacity_reduction > 0
                high_tariff = tariff_rate is not None and rate_mean is not None and tariff_rate > rate_mean
                constraint = (
                    "authorized_emergency_override" if is_override else
                    "transformer_capacity_protection" if overloaded else
                    "high_tariff_peak_reduction" if high_tariff else
                    "comfort_preference_tradeoff" if comfort_score is not None and comfort_score < 1.0 else
                    "peak_load_reduction"
                )
                tags = ["OPTIMIZED_STRATEGY", "FLEXIBLE_LOAD_REDUCED"]
                if context.appliances:
                    tags.append("APPLIANCE_FLEXIBILITY")
                if high_tariff:
                    tags.append("HIGH_TARIFF_PERIOD")
                if comfort_score is not None:
                    tags.append("WITHIN_HARD_COMFORT_BOUNDS")
                    if comfort_score > 0.8:
                        tags.append("COMFORT_PRESERVED")
                if is_override:
                    tags.extend(("EMERGENCY_OVERRIDE", f"OVERRIDE_OPERATOR:{context.emergency_override.operator_id}",
                                 f"OVERRIDE_JUSTIFICATION:{context.emergency_override.justification}"))
                decision = Decision(
                    id=f"{context.dr_event.id}-{building.id}", dr_event_id=context.dr_event.id,
                    building_id=building_id, slot_index=event_slot, action=action,
                    triggering_constraint=constraint, objective_weights_used=dict(context.objective_weights),
                    occupant_id=occupants[0].id if occupants else None,
                    target_variable="flexible_load_kw", before_value=building.flexible_load_kw,
                    after_value=after_load, reasoning_tags=tuple(tags), is_override=is_override,
                    estimated_reduction_kw=reduction_kw, comfort_score=comfort_score,
                )
            else:
                tags = ["OPTIMIZED_STRATEGY", "UNCHANGED_DECISION"]
                if comfort_caps.get(building_id, 0.0) < comfort_sensitive_loads.get(building_id, 0.0):
                    tags.append("COMFORT_PROTECTED")
                if context.appliances and not any(a.is_flexible and a.is_running for a in appliances_by_building.get(building_id, [])):
                    tags.append("NO_ACTIVE_FLEXIBLE_APPLIANCE")
                decision = Decision(
                    id=f"{context.dr_event.id}-{building.id}", dr_event_id=context.dr_event.id,
                    building_id=building_id, slot_index=event_slot, action=ActionType.NO_ACTION,
                    triggering_constraint="comfort_preservation" if "COMFORT_PROTECTED" in tags else "no_change_needed",
                    objective_weights_used=dict(context.objective_weights),
                    occupant_id=occupants[0].id if occupants else None,
                    before_value=building.flexible_load_kw, after_value=building.flexible_load_kw,
                    reasoning_tags=tuple(tags), estimated_reduction_kw=0.0,
                    comfort_score=comfort_score,
                )
            decisions.append(decision)

        for appliance_id, new_slot in outcome.appliance_slots.items():
            appliance = schedulable_by_id[appliance_id]
            if new_slot == appliance.preferred_slot:
                continue
            moved_out_of_event = appliance.preferred_slot in event_slots and new_slot not in event_slots
            before_rate = context.tariff.rate_per_slot.get(appliance.preferred_slot) if context.tariff else None
            after_rate = context.tariff.rate_per_slot.get(new_slot) if context.tariff else None
            tags = ["APPLIANCE_FLEXIBILITY"]
            if moved_out_of_event:
                tags.append("TRANSFORMER_PEAK_PROTECTION")
            if before_rate is not None and after_rate is not None:
                tags.append("TARIFF_BASED_SHIFT" if after_rate < before_rate else "TARIFF_COST_TRADEOFF")
            is_override = str(appliance.building_id) in override_ids
            if is_override:
                tags.extend(("EMERGENCY_OVERRIDE",
                             f"OVERRIDE_OPERATOR:{context.emergency_override.operator_id}",
                             f"OVERRIDE_JUSTIFICATION:{context.emergency_override.justification}"))
            decisions.append(Decision(
                id=f"{context.dr_event.id}-{appliance.id}", dr_event_id=context.dr_event.id,
                building_id=str(appliance.building_id),
                occupant_id=next((o.id for o in occupants_by_building.get(str(appliance.building_id), [])), None),
                slot_index=new_slot,
                action=ActionType.OVERRIDE_APPLIED if is_override else ActionType.DEFER_APPLIANCE,
                target_variable=appliance.id, before_value=float(appliance.preferred_slot),
                after_value=float(new_slot),
                triggering_constraint=("authorized_emergency_override" if is_override else
                    "transformer_capacity_protection" if moved_out_of_event else
                    "tariff_based_appliance_shift"),
                objective_weights_used=dict(context.objective_weights), reasoning_tags=tuple(tags),
                is_override=is_override,
                estimated_reduction_kw=appliance.rated_power_kw if moved_out_of_event else 0.0,
            ))
        return decisions

    @staticmethod
    def _opt_out_decision(context: PlanningContext, building_id: str) -> Decision:
        return Decision(
            id=f"{context.dr_event.id}-{building_id}", dr_event_id=context.dr_event.id,
            building_id=str(building_id), slot_index=0, action=ActionType.OPT_OUT_RESPECTED,
            triggering_constraint="occupant_opt_out", objective_weights_used=dict(context.objective_weights),
            target_variable=None, reasoning_tags=("OPTED_OUT", "PROTECTED_DECISION"),
        )

    @staticmethod
    def _infeasible_decision(context: PlanningContext, building_id: str, status: str) -> Decision:
        return Decision(
            id=f"{context.dr_event.id}-{building_id}", dr_event_id=context.dr_event.id,
            building_id=str(building_id), slot_index=0, action=ActionType.NO_ACTION,
            triggering_constraint="insufficient_reduction_capacity",
            objective_weights_used=dict(context.objective_weights),
            reasoning_tags=("INFEASIBLE_REQUEST", f"SOLVER_STATUS:{status}"),
        )
