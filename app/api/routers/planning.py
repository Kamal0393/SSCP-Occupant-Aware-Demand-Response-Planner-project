from fastapi import APIRouter

from app.api.schemas.decision import DecisionSchema
from app.api.schemas.planning import (
    PlanningRequestSchema,
    PlanningResponseSchema,
)
from app.application.dto.planning_mapper import to_domain_context
from app.application.services.planning_service import PlanningService
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.infrastructure.solver.ortools_solver import ORToolsSolver

router = APIRouter()

_planning_service = PlanningService(
    strategy=OptimizedStrategy(solver=ORToolsSolver())
)


@router.post(
    "/generate",
    response_model=PlanningResponseSchema,
    response_model_exclude_none=False,
)
def generate_plan(request: PlanningRequestSchema) -> PlanningResponseSchema:
    context = to_domain_context(request)

    decisions = _planning_service.generate_plan(context)

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
            )
            for decision in decisions
        ]
    )