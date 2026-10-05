from dataclasses import dataclass
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.transformer import Transformer

from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import Decision
from app.application.services.planning_analysis_service import PlanningAnalysisService, PlanningMetrics


@dataclass(frozen=True)
class StrategyComparison:
    """Result of running and comparing two demand-response strategies."""

    first_strategy_name: str
    first_decisions: tuple[Decision, ...]
    second_strategy_name: str
    second_decisions: tuple[Decision, ...]
    metrics: PlanningMetrics | None = None
    first_metrics: PlanningMetrics | None = None
    comparison_metrics: dict[str, float | int | None] | None = None

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

        analyzable = (
            isinstance(getattr(context, "transformer", None), Transformer)
            and isinstance(getattr(context, "dr_event", None), DemandResponseEvent)
        )
        baseline_metrics = PlanningAnalysisService().analyze(context, first_decisions) if analyzable else None
        optimized_metrics = PlanningAnalysisService().analyze(context, second_decisions) if analyzable else None
        comparison_metrics = None
        if baseline_metrics is not None and optimized_metrics is not None:
            peak_change = baseline_metrics.optimized_peak_load_kw - optimized_metrics.optimized_peak_load_kw
            comparison_metrics = {
                "baseline_peak_load_kw": baseline_metrics.optimized_peak_load_kw,
                "optimized_peak_load_kw": optimized_metrics.optimized_peak_load_kw,
                "peak_reduction_kw": peak_change,
                "peak_reduction_pct": (
                    peak_change / baseline_metrics.optimized_peak_load_kw * 100.0
                    if baseline_metrics.optimized_peak_load_kw else 0.0
                ),
                "comfort_metric_change": (
                    optimized_metrics.comfort_metric - baseline_metrics.comfort_metric
                    if optimized_metrics.comfort_metric is not None
                    and baseline_metrics.comfort_metric is not None else None
                ),
                "estimated_cost_difference_change": (
                    optimized_metrics.estimated_cost_difference - baseline_metrics.estimated_cost_difference
                    if optimized_metrics.estimated_cost_difference is not None
                    and baseline_metrics.estimated_cost_difference is not None else None
                ),
                "opted_out_decision_count_change": (
                    optimized_metrics.opted_out_decision_count - baseline_metrics.opted_out_decision_count
                ),
                "stakeholder_objective_value_change": (
                    optimized_metrics.stakeholder_objective_value - baseline_metrics.stakeholder_objective_value
                    if optimized_metrics.stakeholder_objective_value is not None
                    and baseline_metrics.stakeholder_objective_value is not None else None
                ),
            }

        return StrategyComparison(
            first_strategy_name=self._first_strategy.strategy_name,
            first_decisions=tuple(first_decisions),
            second_strategy_name=self._second_strategy.strategy_name,
            second_decisions=tuple(second_decisions),
            metrics=optimized_metrics,
            first_metrics=baseline_metrics,
            comparison_metrics=comparison_metrics,
        )
