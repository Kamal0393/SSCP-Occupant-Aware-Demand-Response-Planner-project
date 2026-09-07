from dataclasses import dataclass

from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import Decision


@dataclass(frozen=True)
class StrategyComparison:
    """Result of running and comparing two demand-response strategies."""

    first_strategy_name: str
    first_decisions: tuple[Decision, ...]
    second_strategy_name: str
    second_decisions: tuple[Decision, ...]

    @property
    def first_total_reduction_kw(self) -> float:
        return sum(
            decision.estimated_reduction_kw
            for decision in self.first_decisions
        )

    @property
    def second_total_reduction_kw(self) -> float:
        return sum(
            decision.estimated_reduction_kw
            for decision in self.second_decisions
        )

    @property
    def reduction_difference_kw(self) -> float:
        return (
            self.second_total_reduction_kw
            - self.first_total_reduction_kw
        )

    @property
    def first_override_count(self) -> int:
        return sum(
            decision.is_override
            for decision in self.first_decisions
        )

    @property
    def second_override_count(self) -> int:
        return sum(
            decision.is_override
            for decision in self.second_decisions
        )

    @property
    def changed_decision_count(self) -> int:
        first_by_target = {
            (
                decision.building_id,
                decision.occupant_id,
                decision.slot_index,
            ): decision
            for decision in self.first_decisions
        }

        second_by_target = {
            (
                decision.building_id,
                decision.occupant_id,
                decision.slot_index,
            ): decision
            for decision in self.second_decisions
        }

        all_targets = set(first_by_target) | set(second_by_target)

        return sum(
            first_by_target.get(target) != second_by_target.get(target)
            for target in all_targets
        )


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