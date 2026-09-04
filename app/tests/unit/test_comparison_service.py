from unittest.mock import Mock

from app.application.services.comparison_service import (
    ComparisonService,
    StrategyComparison,
)
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import ActionType, Decision
from app.domain.strategies.baseline_strategy import BaselineStrategy
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.infrastructure.solver.ortools_solver import ORToolsSolver




def make_decision(decision_id: str) -> Decision:
    return Decision(
        id=decision_id,
        dr_event_id="event-1",
        building_id="building-1",
        slot_index=0,
        action=ActionType.NO_ACTION,
        triggering_constraint="none",
        objective_weights_used={
            "peak_reduction": 0.5,
            "comfort": 0.5,
        },
    )


def test_comparison_service_runs_both_strategies() -> None:
    context = Mock(spec=PlanningContext)

    first = Mock()
    first.strategy_name = "baseline"
    first.generate_plan.return_value = [make_decision("baseline-1")]

    second = Mock()
    second.strategy_name = "optimized"
    second.generate_plan.return_value = [make_decision("optimized-1")]

    service = ComparisonService(first, second)

    result = service.compare(context)

    assert isinstance(result, StrategyComparison)
    assert result.first_strategy_name == "baseline"
    assert result.second_strategy_name == "optimized"
    assert result.first_decisions[0].id == "baseline-1"
    assert result.second_decisions[0].id == "optimized-1"

    first.generate_plan.assert_called_once_with(context)
    second.generate_plan.assert_called_once_with(context)

def test_comparison_calculates_reduction_difference() -> None:
    first = Mock()
    first.strategy_name = "baseline"
    first.generate_plan.return_value = [
        make_decision("baseline-1")
    ]

    second = Mock()
    second.strategy_name = "optimized"

    optimized_decision = Decision(
        id="optimized-1",
        dr_event_id="event-1",
        building_id="building-1",
        slot_index=0,
        action=ActionType.REDUCE_SETPOINT,
        triggering_constraint="transformer_overload_hard_limit",
        objective_weights_used={
            "peak_reduction": 0.7,
            "comfort": 0.3,
        },
        estimated_reduction_kw=2.5,
    )

    second.generate_plan.return_value = [optimized_decision]

    service = ComparisonService(first, second)
    result = service.compare(Mock(spec=PlanningContext))

    assert result.first_total_reduction_kw == 0.0
    assert result.second_total_reduction_kw == 2.5
    assert result.reduction_difference_kw == 2.5


def test_comparison_counts_overrides() -> None:
    first = Mock()
    first.strategy_name = "baseline"
    first.generate_plan.return_value = [
        make_decision("baseline-1")
    ]

    second = Mock()
    second.strategy_name = "optimized"

    override_decision = Decision(
        id="optimized-1",
        dr_event_id="event-1",
        building_id="building-1",
        slot_index=0,
        action=ActionType.OVERRIDE_APPLIED,
        triggering_constraint="authorized_override",
        objective_weights_used={
            "peak_reduction": 0.5,
            "comfort": 0.5,
        },
        is_override=True,
    )

    second.generate_plan.return_value = [override_decision]

    service = ComparisonService(first, second)
    result = service.compare(Mock(spec=PlanningContext))

    assert result.first_override_count == 0
    assert result.second_override_count == 1

def test_comparison_service_compares_real_strategies() -> None:
    context = PlanningContext(
        dr_event=Mock(
            target_reduction_kw=6.0,
            id="DR1",
        ),
        transformer=Mock(),
        buildings=(
            Mock(
                id=1,
                flexible_load_kw=5.0,
            ),
            Mock(
                id=2,
                flexible_load_kw=5.0,
            ),
        ),
        occupants=(),
        comfort_ranges={},
        tariff=None,
    )

    service = ComparisonService(
    BaselineStrategy(),
    OptimizedStrategy(ORToolsSolver()),
    )

    result = service.compare(context)

    assert result.first_strategy_name == "baseline"
    assert result.second_strategy_name == "optimized"

    assert result.first_total_reduction_kw == 6.0
    assert result.second_total_reduction_kw == 6.0

    assert result.reduction_difference_kw == 0.0

    assert len(result.first_decisions) == 2
    assert len(result.second_decisions) == 2

def test_comparison_counts_changed_decisions() -> None:
    first = Mock()
    first.strategy_name = "baseline"

    first_decision = make_decision("baseline-1")
    first.generate_plan.return_value = [first_decision]

    second = Mock()
    second.strategy_name = "optimized"

    second_decision = Decision(
        id="optimized-1",
        dr_event_id="event-1",
        building_id="building-1",
        slot_index=0,
        action=ActionType.REDUCE_SETPOINT,
        triggering_constraint="transformer_overload_hard_limit",
        objective_weights_used={
            "peak_reduction": 0.7,
            "comfort": 0.3,
        },
        estimated_reduction_kw=2.0,
    )
    second.generate_plan.return_value = [second_decision]

    service = ComparisonService(first, second)

    result = service.compare(Mock(spec=PlanningContext))

    assert result.changed_decision_count == 1
