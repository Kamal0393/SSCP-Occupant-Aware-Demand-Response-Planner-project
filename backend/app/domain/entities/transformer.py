"""
Module: transformer.py

Purpose:
    Defines the Transformer entity representing a neighbourhood distribution
    transformer that can become overloaded when connected buildings draw more
    load than its rated capacity. This is the root cause the entire project
    exists to mitigate.

Design decisions:
    - `rated_capacity_kw` and `current_load_kw` are kept separate so the
      overload ratio can be computed on demand rather than stored redundantly
      (avoids stale-state bugs).
    - `is_overloaded` and `overload_kw` are derived properties, not stored
      fields, so there is exactly one source of truth for "how bad is it".
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Transformer:
    """
    A neighbourhood distribution transformer.

    Attributes:
        id: Unique transformer identifier.
        name: Human-readable label (e.g. "Transformer T-14, Sector 7").
        rated_capacity_kw: Maximum safe sustained load.
        current_load_kw: Present aggregate load from all connected buildings.
        connected_building_ids: Buildings drawing power from this transformer.
        safety_margin_pct: Operating margin below rated capacity that the
            utility wants to maintain even outside of active DR events
            (e.g. 0.1 -> operator wants load kept below 90% of capacity).
    """

    id: str
    name: str
    rated_capacity_kw: float
    current_load_kw: float
    connected_building_ids: tuple[str, ...] = field(default_factory=tuple)
    safety_margin_pct: float = 0.10

    def __post_init__(self) -> None:
        if self.rated_capacity_kw <= 0:
            raise ValueError(f"Transformer {self.id}: rated_capacity_kw must be positive")
        if self.current_load_kw < 0:
            raise ValueError(f"Transformer {self.id}: current_load_kw cannot be negative")
        if not 0 <= self.safety_margin_pct < 1:
            raise ValueError(f"Transformer {self.id}: safety_margin_pct must be in [0, 1)")

    @property
    def safe_operating_limit_kw(self) -> float:
        """Load threshold the utility wants to stay under, even off-event."""
        return self.rated_capacity_kw * (1 - self.safety_margin_pct)

    @property
    def is_overloaded(self) -> bool:
        return self.current_load_kw > self.rated_capacity_kw

    @property
    def overload_kw(self) -> float:
        """Magnitude of overload; 0 if not overloaded."""
        return max(0.0, self.current_load_kw - self.rated_capacity_kw)

    @property
    def utilization_pct(self) -> float:
        return self.current_load_kw / self.rated_capacity_kw
