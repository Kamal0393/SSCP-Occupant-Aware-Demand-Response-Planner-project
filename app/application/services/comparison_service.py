from dataclasses import dataclass

from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import Decision


@dataclass(frozen=True)
class StrategyComparison:
    """Result of running two demand-response strategies."""

    first_strategy_name: str
    first_decisions: tuple[Decision, ...]
    second_strategy_name: str
    second_decisions: tuple[Decision, ...]


class ComparisonService:
    """Application service responsible for comparing two planning strategies."""

    def __init__(
        self,
        first_strategy: DemandResponseStrategy,
        second_strategy: DemandResponseStrategy,
    ) -> None:
        self._first_strategy = first_strategy
        self._second_strategy = second_strategy

    def compare(
        self,
        context: PlanningContext,
    ) -> StrategyComparison:
        first_decisions = self._first_strategy.generate_plan(context)
        second_decisions = self._second_strategy.generate_plan(context)

        return StrategyComparison(
            first_strategy_name=self._first_strategy.strategy_name,
            first_decisions=tuple(first_decisions),
            second_strategy_name=self._second_strategy.strategy_name,
            second_decisions=tuple(second_decisions),
        )
    