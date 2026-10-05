"""Persistence-facing contracts and records; deliberately outside the domain."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    @abstractmethod
    def add(self, entity: T) -> T: ...

    @abstractmethod
    def get(self, entity_id: str) -> T | None: ...

    @abstractmethod
    def list(self) -> list[T]: ...

    @abstractmethod
    def delete(self, entity_id: str) -> bool: ...


@dataclass(frozen=True)
class PlanningResultRecord:
    id: str
    dr_event_id: str
    strategy_name: str
    status: str = "completed"
    objective_weights: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class ExplanationRecord:
    id: str
    decision_id: str
    text: str
    generated_at: datetime | None = None


@dataclass(frozen=True)
class PlanningHistoryRecord:
    id: int | None
    planning_result_id: str
    action: str
    actor: str = "system"
    details: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None
