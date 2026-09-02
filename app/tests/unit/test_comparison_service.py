from unittest.mock import Mock

from app.application.services.comparison_service import (
    ComparisonService,
    StrategyComparison,
)
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import ActionType, Decision


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
    