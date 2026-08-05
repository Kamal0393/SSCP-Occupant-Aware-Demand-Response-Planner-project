"""
Module: building.py

Purpose:
    Defines the Building entity - a physical structure connected to a single
    neighbourhood transformer, containing one or more occupants and appliances
    whose load can be shaped during a demand-response event.

Design decisions:
    - Building is immutable (frozen dataclass). A DR planning run should never
      mutate the entities it reasons about; instead, the planner emits Decision
      objects describing proposed changes, and a separate apply step (outside
      the domain layer) commits them.
    - `flexible_load_kw` and `fixed_load_kw` are separated explicitly because
      the optimizer must never touch fixed (non-shiftable) load - this is a
      hard constraint baked into the data model, not just the solver logic.
"""

from dataclasses import dataclass, field
from enum import Enum


class BuildingType(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"


@dataclass(frozen=True)
class Building:
    """
    A single building connected to a neighbourhood transformer.

    Attributes:
        id: Unique building identifier.
        name: Human-readable label (e.g. "Block C, Unit 4B").
        transformer_id: The transformer this building draws power from.
        building_type: Residential / commercial / mixed use.
        floor_area_sqm: Used for load normalisation and reporting.
        fixed_load_kw: Baseline load that cannot be shifted or reduced
            (e.g. refrigeration, medical equipment, security systems).
        flexible_load_kw: Load that the planner is allowed to reason about
            (e.g. HVAC, water heating, EV charging, deferrable appliances).
        occupant_ids: Occupants associated with this building.
    """

    id: str
    name: str
    transformer_id: str
    building_type: BuildingType
    floor_area_sqm: float
    fixed_load_kw: float
    flexible_load_kw: float
    occupant_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.floor_area_sqm <= 0:
            raise ValueError(f"Building {self.id}: floor_area_sqm must be positive")
        if self.fixed_load_kw < 0 or self.flexible_load_kw < 0:
            raise ValueError(f"Building {self.id}: load values cannot be negative")

    @property
    def total_load_kw(self) -> float:
        """Total instantaneous demand this building can present to the grid."""
        return self.fixed_load_kw + self.flexible_load_kw
