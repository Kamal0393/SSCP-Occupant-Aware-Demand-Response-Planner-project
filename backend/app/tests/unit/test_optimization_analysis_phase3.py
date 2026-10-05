from dataclasses import replace
from datetime import datetime, timedelta

from app.application.services.explanation_service import ExplanationService
from app.application.services.planning_analysis_service import PlanningAnalysisService
from app.api.schemas.planning import ObjectiveWeightsSchema
from app.domain.entities.appliance import Appliance, ApplianceType
from app.domain.entities.building import Building, BuildingType
from app.domain.entities.dr_event import DemandResponseEvent, DREventStatus
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.decision import ActionType
from app.domain.value_objects.emergency_override import EmergencyOverride
from app.domain.value_objects.load_profile import LoadProfile
from app.infrastructure.solver.ortools_solver import ORToolsSolver
from pydantic import ValidationError
import pytest


def context(*, current=10, capacity=10, target=2, opted_out=False, allow_override=False,
            comfort=True, appliances=(), tariff=None, override=None, fixed=2, flexible=4):
    event = DemandResponseEvent("DR", "TX", datetime(2026, 1, 1, 18),
                                datetime(2026, 1, 1, 19), target,
                                DREventStatus.ACTIVE if override else DREventStatus.PLANNED)
    building = Building("B", "House", "TX", BuildingType.RESIDENTIAL, 100, fixed, flexible, ("O",))
    occupant = Occupant("O", "B", "Occupant", "CR", opted_out, allow_override)
    ranges = {"CR": ComfortRange("CR", "temperature_c", 20, 24, 22)} if comfort else {}
    return PlanningContext(event, Transformer("TX", "TX", capacity, current, ("B",)),
        (building,), (occupant,), ranges, tariff, {"peak_reduction": .7, "comfort": .3},
        tuple(appliances), override)


def test_capacity_protection_and_comfort_bounds_are_enforced():
    plan_context = context(current=14, capacity=10, target=2)
    decisions = OptimizedStrategy(ORToolsSolver()).generate_plan(plan_context)
    decision = decisions[0]
    assert decision.estimated_reduction_kw >= 4.0
    assert decision.triggering_constraint == "transformer_capacity_protection"
    assert decision.comfort_score is not None
    assert 0 <= decision.comfort_score <= 1


def test_event_load_profile_drives_capacity_and_actual_peak_energy_metrics():
    base = context(current=10, capacity=10, target=2, flexible=4)
    profile = [10.0] * 96
    profile[72] = 14.0
    profiled_context = PlanningContext(
        base.dr_event, base.transformer, base.buildings, base.occupants,
        base.comfort_ranges, base.tariff, base.objective_weights,
        transformer_load_profile=LoadProfile("TX", tuple(profile)),
    )
    decisions = OptimizedStrategy(ORToolsSolver()).generate_plan(profiled_context)
    metrics = PlanningAnalysisService().analyze(profiled_context, decisions)
    assert metrics.baseline_peak_load_kw == 14.0
    assert metrics.optimized_peak_load_kw == 10.0
    assert metrics.peak_reduction_kw == 4.0
    assert metrics.baseline_energy_kwh == 11.0
    assert metrics.optimized_energy_kwh == 7.0


def test_infeasible_capacity_protection_returns_explainable_decisions():
    plan_context = context(current=20, capacity=10, target=2, flexible=3)
    decisions = OptimizedStrategy(ORToolsSolver()).generate_plan(plan_context)
    assert decisions[0].estimated_reduction_kw == 0
    assert "INFEASIBLE_REQUEST" in decisions[0].reasoning_tags
    assert "infeasible" in ExplanationService().explain(decisions[0]).lower()


def test_emergency_override_requires_request_authorization_and_occupant_consent():
    plan_context = context(current=12, capacity=10, target=2, opted_out=True, allow_override=True,
                           override=EmergencyOverride("operator-7", "Prevent transformer thermal damage"))
    decision = OptimizedStrategy(ORToolsSolver()).generate_plan(plan_context)[0]
    assert decision.action == ActionType.OVERRIDE_APPLIED
    assert decision.is_override
    explanation = ExplanationService().explain(decision)
    assert "operator-7" in explanation
    assert "Prevent transformer thermal damage" in explanation
    assert "comfort hard bounds remain enforced" in explanation


def test_opt_out_remains_protected_without_an_authorized_emergency():
    plan_context = context(current=12, capacity=10, target=2, opted_out=True, allow_override=True)
    decision = OptimizedStrategy(ORToolsSolver()).generate_plan(plan_context)[0]
    assert decision.action == ActionType.OPT_OUT_RESPECTED
    assert decision.estimated_reduction_kw == 0


def test_objective_weights_trade_peak_reduction_against_actual_comfort_headroom():
    base = context(current=10, capacity=10, target=2, comfort=False)
    buildings = (
        Building("B1", "Sensitive", "TX", BuildingType.RESIDENTIAL, 100, 1, 2, ("O1",)),
        Building("B2", "Tolerant", "TX", BuildingType.RESIDENTIAL, 100, 1, 2, ("O2",)),
    )
    occupants = (
        Occupant("O1", "B1", "Sensitive", "CR1"),
        Occupant("O2", "B2", "Tolerant", "CR2"),
    )
    ranges = {
        "CR1": ComfortRange("CR1", "temperature_c", 20, 22, 21),
        "CR2": ComfortRange("CR2", "temperature_c", 20, 26, 21),
    }
    peak_first = PlanningContext(base.dr_event, base.transformer, buildings, occupants,
        ranges, None, {"peak_reduction": 1.0, "comfort": 0.0})
    comfort_first = PlanningContext(base.dr_event, base.transformer, buildings, occupants,
        ranges, None, {"peak_reduction": 0.5, "comfort": 0.5})
    solver = ORToolsSolver()
    peak_plan = OptimizedStrategy(solver).generate_plan(peak_first)
    comfort_plan = OptimizedStrategy(solver).generate_plan(comfort_first)
    assert peak_plan[0].estimated_reduction_kw > comfort_plan[0].estimated_reduction_kw
    assert comfort_plan[1].estimated_reduction_kw > peak_plan[1].estimated_reduction_kw


def test_tariff_scheduler_moves_flexible_task_out_of_dr_window_and_metrics_are_measured():
    washer = Appliance("A1", "B", "Washer", ApplianceType.WASHING_MACHINE,
                       1.5, True, False, preferred_slot=72, max_shift_slots=4)
    rates = {slot: 18.0 for slot in range(96)}
    rates[68] = 5.0
    task_context = context(current=10, capacity=10, target=1, comfort=False,
                           appliances=(washer,), tariff=Tariff("T", "TOU", "INR", rates),
                           fixed=10, flexible=0)
    decisions = OptimizedStrategy(ORToolsSolver()).generate_plan(task_context)
    shift = next(decision for decision in decisions if decision.action == ActionType.DEFER_APPLIANCE)
    assert shift.after_value == 68
    assert shift.estimated_reduction_kw == 1.5
    assert "TARIFF_BASED_SHIFT" in shift.reasoning_tags
    metrics = PlanningAnalysisService().analyze(task_context, decisions)
    assert metrics.baseline_peak_load_kw == 11.5
    assert metrics.optimized_peak_load_kw == 10
    assert round(metrics.peak_reduction_pct, 2) == 13.04
    assert metrics.modified_decision_count == 1
    assert metrics.estimated_cost_difference is not None
    assert round(metrics.estimated_cost_difference, 3) == -4.875


def test_objective_weight_defaults_and_cost_weight_alias():
    defaults = ObjectiveWeightsSchema(peak_reduction=0.5, comfort=0.5)
    custom = ObjectiveWeightsSchema(peak_reduction=0.3, comfort=0.4, cost_weight=0.8)
    assert defaults.energy_cost == 0.25
    assert custom.energy_cost == 0.8


@pytest.mark.parametrize("field", ["comfort", "cost_weight"])
def test_negative_stakeholder_objective_weights_are_rejected(field):
    values = {"peak_reduction": 0.5, "comfort": 0.5, "cost_weight": 0.25}
    values[field] = -0.1
    with pytest.raises(ValidationError):
        ObjectiveWeightsSchema(**values)


def test_analysis_exposes_cost_comfort_metrics_and_combined_objective():
    rates = {slot: 2.0 for slot in range(96)}
    plan_context = replace(
        context(current=14, capacity=10, target=4, flexible=4,
                tariff=Tariff("T", "TOU", "INR", rates)),
        objective_weights={"peak_reduction": 0.7, "comfort": 0.4, "energy_cost": 0.6},
    )
    decisions = OptimizedStrategy(ORToolsSolver()).generate_plan(plan_context)
    metrics = PlanningAnalysisService().analyze(plan_context, decisions)
    assert metrics.comfort_metric is not None
    assert 0 <= metrics.comfort_metric <= 1
    assert metrics.cost_metric is not None
    assert metrics.comfort_weight == 0.4
    assert metrics.cost_weight == 0.6
    assert metrics.stakeholder_objective_value == pytest.approx(
        0.4 * (1 - metrics.comfort_metric) + 0.6 * metrics.cost_metric
    )


def test_cost_weight_changes_appliance_schedule_tradeoff():
    washer = Appliance("A1", "B", "Washer", ApplianceType.WASHING_MACHINE,
                       1.5, True, False, preferred_slot=72, max_shift_slots=4)
    rates = {slot: 100.0 for slot in range(96)}
    rates[68] = 1.0
    base = context(current=10, capacity=10, target=1.5, comfort=False,
                   appliances=(washer,), tariff=Tariff("T", "TOU", "INR", rates),
                   fixed=10, flexible=0)
    comfort_first = replace(base, objective_weights={
        "peak_reduction": 0.7, "comfort": 1.0, "energy_cost": 0.0,
    })
    cost_first = replace(base, objective_weights={
        "peak_reduction": 0.7, "comfort": 1.0, "energy_cost": 10.0,
    })
    solver = ORToolsSolver()
    comfort_shift = next(d for d in OptimizedStrategy(solver).generate_plan(comfort_first)
                         if d.action == ActionType.DEFER_APPLIANCE)
    cost_shift = next(d for d in OptimizedStrategy(solver).generate_plan(cost_first)
                      if d.action == ActionType.DEFER_APPLIANCE)
    assert comfort_shift.after_value == 71
    assert cost_shift.after_value == 68

    comfort_metrics = PlanningAnalysisService().analyze(
        comfort_first, OptimizedStrategy(solver).generate_plan(comfort_first)
    )
    cost_metrics = PlanningAnalysisService().analyze(
        cost_first, OptimizedStrategy(solver).generate_plan(cost_first)
    )
    assert cost_metrics.comfort_metric < comfort_metrics.comfort_metric
    assert cost_metrics.cost_metric < comfort_metrics.cost_metric


def test_extreme_stakeholder_weights_do_not_relax_hard_constraints():
    bounded = replace(
        context(current=12, capacity=10, target=2, flexible=4),
        hvac_setpoint_change_c_per_kw=1.0,
        objective_weights={"peak_reduction": 0.7, "comfort": 0.0, "energy_cost": 100.0},
    )
    bounded_decision = OptimizedStrategy(ORToolsSolver()).generate_plan(bounded)[0]
    assert bounded_decision.estimated_reduction_kw <= 2.0
    assert bounded_decision.comfort_score == 0.0

    opted_out = replace(
        context(current=12, capacity=10, target=2, opted_out=True),
        objective_weights={"peak_reduction": 0.7, "comfort": 0.0, "energy_cost": 100.0},
    )
    opt_out_decision = OptimizedStrategy(ORToolsSolver()).generate_plan(opted_out)[0]
    assert opt_out_decision.action == ActionType.OPT_OUT_RESPECTED
    assert opt_out_decision.estimated_reduction_kw == 0.0
