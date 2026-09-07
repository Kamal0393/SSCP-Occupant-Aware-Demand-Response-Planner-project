"""
Module: hard_constraints.py

Purpose:
    Defines the set of HARD constraints that any strategy (baseline or
    optimized) MUST satisfy. Hard constraints are non-negotiable: a plan that
    violates one is invalid, full stop, regardless of how good it is on the
    objectives. This module defines them declaratively so both the CP-SAT
    solver adapter (Milestone 4) and simple validators can reference the same
    source of truth.

Inputs:
    A candidate Decision (or set of Decisions) plus the domain context
    (occupants, comfort ranges, transformer state) needed to evaluate it.

Outputs:
    HardConstraintViolation exceptions, or silent pass if satisfied.

Design decisions:
    - Constraints are expressed as pure functions, not classes, since they
      have no state of their own - this keeps them trivially unit-testable
      and directly reusable as CP-SAT constraint expressions later.
    - Each constraint function documents which functional requirement it
      satisfies, so the mapping from "mandatory requirement" to "code" is
      traceable for the project documentation deliverable.
"""

from app.core.exceptions import HardConstraintViolationError
from app.domain.entities.occupant import Occupant
from app.domain.value_objects.comfort_range import ComfortRange


def enforce_opt_out(occupant: Occupant, proposed_action_touches_building: bool) -> None:
    """
    Satisfies: "Support occupant opt-out" + "Represent hard constraints".

    An opted-out occupant's building must never be touched by an automated
    decision unless a valid authorized override is separately recorded
    (see override_service.py in the application layer - override is an
    explicit, audited bypass, not a silent exception here).
    """
    if occupant.opted_out and proposed_action_touches_building:
        raise HardConstraintViolationError(
            f"Occupant {occupant.id} has opted out; building {occupant.building_id} "
            f"cannot be modified without an authorized override."
        )


def enforce_comfort_hard_bounds(comfort_range: ComfortRange, proposed_value: float) -> None:
    """
    Satisfies: "Use occupant comfort ranges" + "Represent hard constraints".

    A proposed setpoint must never fall outside the occupant's hard min/max
    bounds, even if doing so would significantly help peak reduction.
    """
    if not comfort_range.is_within_hard_bounds(proposed_value):
        raise HardConstraintViolationError(
            f"Proposed value {proposed_value} for '{comfort_range.variable}' "
            f"falls outside hard comfort bounds "
            f"[{comfort_range.min_value}, {comfort_range.max_value}]"
        )


def enforce_no_negative_load(building_id: str, proposed_load_kw: float) -> None:
    """A building's load can never be reduced below zero - basic physical constraint."""
    if proposed_load_kw < 0:
        raise HardConstraintViolationError(
            f"Building {building_id}: proposed load {proposed_load_kw} kW is negative"
        )
