"""Comparison and persisted planning-analysis endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas.decision import DecisionSchema
from app.api.schemas.planning import PlanningRequestSchema
from app.api.schemas.planning_records import (
    ComparisonResponseSchema, ExplanationResponseSchema,
    PlanningHistoryResponseSchema, PlanningResultResponseSchema,
)
from app.application.dto.planning_mapper import to_domain_context
from app.application.services.comparison_service import ComparisonService
from app.application.services.explanation_service import ExplanationService
from app.core.exceptions import UnauthorizedOverrideError
from app.domain.strategies.baseline_strategy import BaselineStrategy
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.infrastructure.db.models import DecisionModel, ExplanationModel
from app.infrastructure.db.repositories import (
    DecisionRepository, PlanningHistoryRepository, PlanningResultRepository,
)
from app.infrastructure.solver.ortools_solver import ORToolsSolver

router = APIRouter()
_explanations = ExplanationService()


def _decision_payload(decision):
    return DecisionSchema(
        id=decision.id, dr_event_id=decision.dr_event_id,
        building_id=decision.building_id, occupant_id=decision.occupant_id,
        slot_index=decision.slot_index, action=decision.action,
        target_variable=decision.target_variable, before_value=decision.before_value,
        after_value=decision.after_value, triggering_constraint=decision.triggering_constraint,
        objective_weights_used=decision.objective_weights_used,
        reasoning_tags=decision.reasoning_tags, is_override=decision.is_override,
        estimated_reduction_kw=decision.estimated_reduction_kw,
        comfort_score=decision.comfort_score, delta=decision.delta,
        explanation=_explanations.explain(decision),
    ).model_dump(mode="json")


@router.post("/compare", response_model=ComparisonResponseSchema)
def compare_plans(request: PlanningRequestSchema) -> dict:
    if request.emergency_override is not None:
        raise UnauthorizedOverrideError(
            "Emergency overrides cannot be applied during strategy comparison; use the authorized planning route"
        )
    context = to_domain_context(request)
    result = ComparisonService(
        BaselineStrategy(), OptimizedStrategy(solver=ORToolsSolver())
    ).compare(context)
    metrics = result.metrics.to_dict() if result.metrics else None
    if metrics is not None:
        metrics["baseline_strategy"] = result.first_metrics.to_dict() if result.first_metrics else None
        metrics["optimized_strategy"] = result.metrics.to_dict()
        metrics["comparison"] = result.comparison_metrics
    return {
        "first_strategy": result.first_strategy_name,
        "first_decisions": [_decision_payload(d) for d in result.first_decisions],
        "second_strategy": result.second_strategy_name,
        "second_decisions": [_decision_payload(d) for d in result.second_decisions],
        "changed_decision_count": result.changed_decision_count,
        "metrics": metrics,
    }


@router.get("/history", response_model=list[PlanningHistoryResponseSchema])
def list_history(session: Session = Depends(get_db)) -> list[dict]:
    return [item.__dict__ for item in PlanningHistoryRepository(session).list()]


@router.get("/history/{result_id}", response_model=list[PlanningHistoryResponseSchema])
def history_for_result(result_id: str, session: Session = Depends(get_db)) -> list[dict]:
    if PlanningResultRepository(session).get(result_id) is None:
        raise HTTPException(404, detail="Planning result not found")
    return [item.__dict__ for item in PlanningHistoryRepository(session).by_result(result_id)]


@router.get("/results", response_model=list[PlanningResultResponseSchema])
def list_results(session: Session = Depends(get_db)) -> list[dict]:
    return [item.__dict__ for item in PlanningResultRepository(session).list()]


@router.get("/results/{result_id}", response_model=PlanningResultResponseSchema)
def get_result(result_id: str, session: Session = Depends(get_db)) -> dict:
    item = PlanningResultRepository(session).get(result_id)
    if item is None:
        raise HTTPException(404, detail="Planning result not found")
    return item.__dict__


@router.get("/results/{result_id}/explanations", response_model=list[ExplanationResponseSchema])
def explanations(result_id: str, session: Session = Depends(get_db)) -> list[dict]:
    if PlanningResultRepository(session).get(result_id) is None:
        raise HTTPException(404, detail="Planning result not found")
    decisions = DecisionRepository(session).by_result(result_id)
    ids = [d.id for d in decisions]
    if not ids:
        return []
    rows = session.query(ExplanationModel).filter(ExplanationModel.decision_id.in_(ids)).all()
    by_decision = {row.decision_id: row for row in rows}
    return [{"decision_id": d.id, "text": by_decision[d.id].text,
             "generated_at": by_decision[d.id].generated_at}
            for d in decisions if d.id in by_decision]


@router.get("/results/{result_id}/decisions", response_model=list[DecisionSchema])
def result_decisions(result_id: str, session: Session = Depends(get_db)) -> list[dict]:
    if PlanningResultRepository(session).get(result_id) is None:
        raise HTTPException(404, detail="Planning result not found")
    return [_decision_payload(d) for d in DecisionRepository(session).by_result(result_id)]
