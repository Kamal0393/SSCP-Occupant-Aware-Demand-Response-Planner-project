"""
Module: occupant.py

Purpose:
    Defines the Occupant entity representing a person (or household) whose
    comfort, privacy, and scheduling preferences must be respected by the
    demand-response planner. This entity is the anchor point for the
    "occupant-aware" part of the project - every optimization decision that
    touches a building must be traceable back to an occupant's constraints
    and opt-out status.

Design decisions:
    - `opted_out` is a first-class boolean, not inferred from other state.
      An opted-out occupant's building must be treated as a HARD constraint
      (excluded from the optimizer's action space entirely), not a soft
      preference - this directly satisfies the "support occupant opt-out"
      and "represent hard constraints" requirements.
    - `comfort_range_id` references a ComfortRange value object rather than
      embedding it, so comfort preferences can be versioned/updated
      independently of the occupant record (audit trail friendly).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Occupant:
    """
    A person or household occupying a Building.

    Attributes:
        id: Unique occupant identifier.
        building_id: The building this occupant lives/works in.
        display_name: Non-identifying label for UI purposes (privacy-preserving;
            no PII such as full legal name or contact details is stored here).
        comfort_range_id: Reference to this occupant's ComfortRange preferences.
        opted_out: If True, this occupant's building must NEVER be modified by
            an automated demand-response action, regardless of transformer
            overload severity. Enforced as a hard constraint in the solver.
        allow_override: Whether an authorized utility operator may override
            this occupant's opt-out in an emergency (e.g. imminent transformer
            failure). Distinct from opted_out - this is a pre-consented
            emergency escape hatch, not a silent bypass.
    """

    id: str
    building_id: str
    display_name: str
    comfort_range_id: str
    opted_out: bool = False
    allow_override: bool = False
