import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.schemas.decision import DecisionSchema
from app.api.schemas.planning import (
    OverrideOutcomeSchema,
    PlanningRequestSchema,
    PlanningResponseSchema,
)
from app.application.dto.planning_mapper import to_domain_context
from app.application.services.explanation_service import ExplanationService
from app.application.services.planning_analysis_service import PlanningAnalysisService
from app.application.services.planning_persistence_service import PlanningPersistenceService
from app.application.services.planning_service import PlanningService
from app.core.config import settings
from app.core.exceptions import UnauthorizedOverrideError
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.domain.value_objects.emergency_override import EmergencyOverride
from app.infrastructure.db.repositories import (
    DecisionRepository,
    DREventRepository,
    ExplanationRepository,
    PlanningHistoryRepository,
    PlanningResultRepository,
    TransformerRepository,
)
from app.api.dependencies import get_db
from app.infrastructure.solver.ortools_solver import ORToolsSolver

router = APIRouter()

_planning_service = PlanningService(
    strategy=OptimizedStrategy(solver=ORToolsSolver())
)
_explanation_service = ExplanationService()
_analysis_service = PlanningAnalysisService()


@router.post(
    "/emergency-override",
    response_model=PlanningResponseSchema,
    response_model_exclude_none=False,
)
@router.post(
    "/generate",
    response_model=PlanningResponseSchema,
    response_model_exclude_none=False,
)
def generate_plan(
    request: PlanningRequestSchema,
    override_token: str | None = Header(default=None, alias="X-Override-Token"),
    session: Session = Depends(get_db),
) -> PlanningResponseSchema:
    authorized_override = None
    if request.emergency_override is not None:
        configured_token = settings.OVERRIDE_AUTH_TOKEN
        if (not configured_token or not override_token
                or not hmac.compare_digest(configured_token, override_token)):
            raise UnauthorizedOverrideError("A valid operator token is required for emergency override")
        authorized_override = EmergencyOverride(
            request.emergency_override.operator_id,
            request.emergency_override.justification,
        )
    context = to_domain_context(request, emergency_override=authorized_override)

    decisions = _planning_service.generate_plan(context)
    metrics = _analysis_service.analyze(context, decisions)
    override_decisions = [decision for decision in decisions if decision.is_override]
    override_outcome = OverrideOutcomeSchema(
        requested=request.emergency_override is not None,
        authorized=authorized_override is not None,
        applied=bool(override_decisions),
        affected_building_ids=sorted({decision.building_id for decision in override_decisions}),
        explanation=(
            " ".join(_explanation_service.explain(decision) for decision in override_decisions)
            if override_decisions else
            "The override was authorized, but no override action was applied because the plan required none."
            if authorized_override is not None and not metrics.infeasible else
            "The override was authorized, but no feasible override action could be produced."
            if authorized_override is not None else
            "No emergency override was requested."
        ),
    )
    persistence = PlanningPersistenceService(
        transformers=TransformerRepository(session),
        events=DREventRepository(session),
        results=PlanningResultRepository(session),
        decisions=DecisionRepository(session),
        explanations=ExplanationRepository(session),
        history=PlanningHistoryRepository(session),
    )
    try:
        planning_result_id = persistence.record_run(
            context, decisions, metrics, _explanation_service
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return PlanningResponseSchema(
        decisions=[
            DecisionSchema(
                id=decision.id,
                dr_event_id=decision.dr_event_id,
                building_id=decision.building_id,
                occupant_id=decision.occupant_id,
                slot_index=decision.slot_index,
                action=decision.action,
                target_variable=decision.target_variable,
                before_value=decision.before_value,
                after_value=decision.after_value,
                triggering_constraint=decision.triggering_constraint,
                objective_weights_used=decision.objective_weights_used,
                reasoning_tags=decision.reasoning_tags,
                is_override=decision.is_override,
                estimated_reduction_kw=decision.estimated_reduction_kw,
                comfort_score=decision.comfort_score,
                delta=decision.delta,
                explanation=_explanation_service.explain(decision),
            )
            for decision in decisions
        ],
        metrics=metrics.to_dict(),
        planning_result_id=planning_result_id,
        override=override_outcome,
    )
