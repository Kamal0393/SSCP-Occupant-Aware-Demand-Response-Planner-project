"""
Module: dr_event.py

Purpose:
    Defines the DemandResponseEvent entity - a discrete, time-bounded episode
    during which the utility wants to reduce load on a specific transformer.
    All plans (baseline and optimized) are generated in the context of one
    such event.

Design decisions:
    - `target_reduction_kw` is explicit rather than derived, because the
      utility operator may want to request a reduction target that is more
      conservative than the raw overload figure (e.g. planning ahead of a
      forecast overload, not just reacting to a current one).
    - `status` is a simple enum state machine (PLANNED -> ACTIVE -> COMPLETED
      / CANCELLED) which the application layer transitions; the domain layer
      only defines the valid states, not the transition logic itself.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DREventStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DemandResponseEvent:
    """
    A single demand-response episode targeting one transformer.

    Attributes:
        id: Unique event identifier.
        transformer_id: The transformer this event is protecting.
        start_time: Event start (also used to compute the starting time slot).
        end_time: Event end.
        target_reduction_kw: How much load reduction the utility wants
            achieved across the event window.
        status: Current lifecycle state of the event.
    """

    id: str
    transformer_id: str
    start_time: datetime
    end_time: datetime
    target_reduction_kw: float
    status: DREventStatus = DREventStatus.PLANNED

    def __post_init__(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError(f"DR event {self.id}: end_time must be after start_time")
        if self.target_reduction_kw <= 0:
            raise ValueError(f"DR event {self.id}: target_reduction_kw must be positive")

    @property
    def duration_minutes(self) -> float:
        return (self.end_time - self.start_time).total_seconds() / 60
