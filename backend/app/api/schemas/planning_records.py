"""Response contracts for stored planning runs and their audit data."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PlanningResultResponseSchema(BaseModel):
    id: str
    dr_event_id: str
    strategy_name: str
    status: str
    objective_weights: dict[str, float]
    metrics: dict[str, Any]
    created_at: datetime | None = None


class ExplanationResponseSchema(BaseModel):
    decision_id: str
    text: str
    generated_at: datetime | None = None


class PlanningHistoryResponseSchema(BaseModel):
    id: int | None
    planning_result_id: str
    action: str
    actor: str
    details: dict[str, Any]
    occurred_at: datetime | None = None


class ComparisonResponseSchema(BaseModel):
    first_strategy: str
    first_decisions: list[dict[str, Any]]
    second_strategy: str
    second_decisions: list[dict[str, Any]]
    changed_decision_count: int
    metrics: dict[str, Any] | None = None
