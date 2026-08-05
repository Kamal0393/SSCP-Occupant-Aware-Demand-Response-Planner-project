"""
Module: soft_constraints.py

Purpose:
    Defines SOFT constraints/preferences - things the planner should try to
    respect but may trade off against other objectives when necessary. Unlike
    hard constraints, violating a soft constraint doesn't invalidate a plan;
    it costs the plan a penalty that the optimizer weighs against its gains.

Inputs:
    Candidate values plus occupant/schedule context.

Outputs:
    A penalty score in [0, 1] (0 = fully respected, 1 = fully violated) for
    each soft constraint, to be combined into the optimizer's weighted
    objective function.

Design decisions:
    - Soft constraints return continuous penalties, not booleans, so the
      optimizer has a gradient to work with rather than a cliff - this is
      what makes "comfort vs peak reduction" an actual trade-off the UI can
      visualize, rather than a binary pass/fail.
"""

from app.domain.value_objects.comfort_range import ComfortRange


def comfort_preference_penalty(comfort_range: ComfortRange, proposed_value: float) -> float:
    """
    Satisfies: "Represent soft constraints" + comfort objective.

    Penalty for deviating from an occupant's *preferred* value, even while
    staying within hard bounds. 0.0 = at preferred value, 1.0 = at a hard
    bound edge.
    """
    return 1.0 - comfort_range.comfort_score(proposed_value)


def schedule_preference_penalty(preferred_slot: int, proposed_slot: int, max_shift_slots: int) -> float:
    """
    Satisfies: "Keep preferred schedules" (occupant stakeholder objective).

    Penalty for shifting a deferrable appliance/task away from its preferred
    time slot (e.g. delaying a washing machine cycle). Scales linearly with
    distance, capped at 1.0.
    """
    if max_shift_slots <= 0:
        return 0.0 if proposed_slot == preferred_slot else 1.0
    distance = abs(proposed_slot - preferred_slot)
    return min(1.0, distance / max_shift_slots)
