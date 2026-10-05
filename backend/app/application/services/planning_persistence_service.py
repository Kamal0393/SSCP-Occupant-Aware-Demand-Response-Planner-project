"""Coordinates persistence of an executed planning run through repository ports."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from app.application.services.explanation_service import ExplanationService
from app.application.services.planning_analysis_service import PlanningMetrics
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import Decision


@dataclass(frozen=True)
class _PlanningResultData:
    id: str
    dr_event_id: str
    strategy_name: str
    status: str
    objective_weights: dict
    metrics: dict
    created_at: datetime | None = None


@dataclass(frozen=True)
class _ExplanationData:
    id: str
    decision_id: str
    text: str
    generated_at: datetime | None = None


@dataclass(frozen=True)
class _HistoryData:
    id: int | None
    planning_result_id: str
    action: str
    actor: str = "system"
    details: dict = field(default_factory=dict)
    occurred_at: datetime | None = None


class _AddRepository(Protocol):
    def add(self, entity: Any) -> Any: ...


class _DecisionRepository(Protocol):
    def add_for_result(self, entity: Decision, planning_result_id: str) -> Decision: ...


class PlanningPersistenceService:
    def __init__(
        self,
        *,
        transformers: _AddRepository,
        events: _AddRepository,
        results: _AddRepository,
        decisions: _DecisionRepository,
        explanations: _AddRepository,
        history: _AddRepository,
    ) -> None:
        self._transformers = transformers
        self._events = events
        self._results = results
        self._decisions = decisions
        self._explanations = explanations
        self._history = history

    def record_run(
        self,
        context: PlanningContext,
        decisions: list[Decision],
        metrics: PlanningMetrics,
        explanation_service: ExplanationService,
    ) -> str:
        run_id = str(uuid4())
        # Planning results refer to a persisted event, which in turn requires its transformer.
        self._transformers.add(context.transformer)
        self._events.add(context.dr_event)
        self._results.add(_PlanningResultData(
            id=run_id,
            dr_event_id=context.dr_event.id,
            strategy_name="optimized",
            status="infeasible" if metrics.infeasible else "completed",
            objective_weights=dict(context.objective_weights),
            metrics=metrics.to_dict(),
        ))
        self._history.add(_HistoryData(
            id=None, planning_result_id=run_id, action="planning_run_generated",
            details={"decision_count": len(decisions), "infeasible": metrics.infeasible},
        ))

        for decision in decisions:
            # Decision identifiers are unique per run, while API decisions remain stable.
            persisted_decision = replace(decision, id=f"{run_id}:{decision.id}")
            self._decisions.add_for_result(persisted_decision, run_id)
            explanation = explanation_service.explain(decision)
            self._explanations.add(_ExplanationData(
                id=f"explanation:{run_id}:{decision.id}",
                decision_id=persisted_decision.id,
                text=explanation,
            ))
            if decision.is_override:
                tags = decision.reasoning_tags
                self._history.add(_HistoryData(
                    id=None, planning_result_id=run_id, action="emergency_override_applied",
                    actor=next((tag.split(":", 1)[1] for tag in tags
                                if tag.startswith("OVERRIDE_OPERATOR:")), "operator"),
                    details={
                        "decision_id": persisted_decision.id,
                        "building_id": decision.building_id,
                        "justification": next((tag.split(":", 1)[1] for tag in tags
                                               if tag.startswith("OVERRIDE_JUSTIFICATION:")), ""),
                    },
                ))
        return run_id
