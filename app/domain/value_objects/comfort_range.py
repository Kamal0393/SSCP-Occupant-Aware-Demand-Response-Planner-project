"""
Module: comfort_range.py

Purpose:
    Defines ComfortRange, the value object encoding an occupant's acceptable
    envelope for a controllable variable (most commonly temperature). This is
    the primary mechanism by which "soft constraints" and the comfort
    objective are represented in the domain model.

Design decisions:
    - `preferred_value` is distinct from the midpoint of (min, max). Occupants
      may prefer 21C but tolerate 19-24C - the comfort *score* penalizes
      distance from preferred_value, not just range violation, which gives
      the optimizer a smooth gradient to reason about rather than a step
      function.
    - `comfort_score()` returns a value in [0, 1] so it can be combined
      uniformly with other normalized objective terms (cost, satisfaction)
      in the multi-objective weighting used by the optimizer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComfortRange:
    """
    Acceptable envelope for a single controllable comfort variable.

    Attributes:
        id: Unique identifier for this comfort profile.
        variable: Name of the controlled variable (e.g. "temperature_c").
        min_value: Hard lower bound - the optimizer must never propose a
            value below this (hard constraint).
        max_value: Hard upper bound (hard constraint).
        preferred_value: The occupant's ideal setpoint (soft target).
    """

    id: str
    variable: str
    min_value: float
    max_value: float
    preferred_value: float

    def __post_init__(self) -> None:
        if self.min_value >= self.max_value:
            raise ValueError(
                f"ComfortRange {self.id}: min_value must be < max_value "
                f"(got min={self.min_value}, max={self.max_value})"
            )
        if not (self.min_value <= self.preferred_value <= self.max_value):
            raise ValueError(
                f"ComfortRange {self.id}: preferred_value must lie within [min_value, max_value]"
            )

    def is_within_hard_bounds(self, value: float) -> bool:
        """Hard constraint check - used directly by the solver's constraint set."""
        return self.min_value <= value <= self.max_value

    def comfort_score(self, value: float) -> float:
        """
        Soft comfort score in [0, 1], where 1.0 = exactly at preferred_value
        and 0.0 = at or beyond a hard bound. Used as an objective term and
        surfaced directly on the UI as the "Comfort indicator".
        """
        if not self.is_within_hard_bounds(value):
            return 0.0
        if value == self.preferred_value:
            return 1.0
        span = (
            self.max_value - self.preferred_value
            if value > self.preferred_value
            else self.preferred_value - self.min_value
        )
        if span == 0:
            return 0.0
        distance = abs(value - self.preferred_value)
        return max(0.0, 1.0 - (distance / span))
