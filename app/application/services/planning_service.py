from app.domain.strategies.baseline_strategy import BaselineStrategy
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import Decision


class PlanningService:
    """Application service responsible for executing a planning strategy."""

    def __init__(self, strategy: DemandResponseStrategy | None = None) -> None:
        self._strategy = strategy or OptimizedStrategy()

    def generate_plan(
        self,
        context: PlanningContext,
    ) -> list[Decision]:
        return self._strategy.generate_plan(context)