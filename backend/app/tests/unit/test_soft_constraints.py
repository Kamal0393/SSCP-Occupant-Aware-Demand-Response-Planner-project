import pytest

from app.domain.constraints.soft_constraints import (
    comfort_preference_penalty,
    schedule_preference_penalty,
)
from app.domain.value_objects.comfort_range import ComfortRange


def test_comfort_preference_penalty_is_zero_at_preferred_value():
    comfort_range = ComfortRange(
        id="comfort-1",
        variable="temperature_c",
        min_value=19.0,
        max_value=24.0,
        preferred_value=21.0,
    )

    penalty = comfort_preference_penalty(comfort_range, 21.0)

    assert penalty == 0.0


def test_comfort_preference_penalty_reaches_one_at_hard_bound():
    comfort_range = ComfortRange(
        id="comfort-1",
        variable="temperature_c",
        min_value=19.0,
        max_value=24.0,
        preferred_value=21.0,
    )

    lower_penalty = comfort_preference_penalty(comfort_range, 19.0)
    upper_penalty = comfort_preference_penalty(comfort_range, 24.0)

    assert lower_penalty == 1.0
    assert upper_penalty == 1.0


def test_comfort_preference_penalty_increases_with_distance():
    comfort_range = ComfortRange(
        id="comfort-1",
        variable="temperature_c",
        min_value=19.0,
        max_value=24.0,
        preferred_value=21.0,
    )

    near_penalty = comfort_preference_penalty(comfort_range, 22.0)
    far_penalty = comfort_preference_penalty(comfort_range, 23.0)

    assert 0.0 < near_penalty < far_penalty < 1.0


def test_comfort_preference_penalty_is_one_outside_hard_bounds():
    comfort_range = ComfortRange(
        id="comfort-1",
        variable="temperature_c",
        min_value=19.0,
        max_value=24.0,
        preferred_value=21.0,
    )

    penalty = comfort_preference_penalty(comfort_range, 25.0)

    assert penalty == 1.0


def test_schedule_preference_penalty_is_zero_at_preferred_slot():
    penalty = schedule_preference_penalty(
        preferred_slot=5,
        proposed_slot=5,
        max_shift_slots=4,
    )

    assert penalty == 0.0


def test_schedule_preference_penalty_scales_linearly():
    penalty = schedule_preference_penalty(
        preferred_slot=5,
        proposed_slot=7,
        max_shift_slots=4,
    )

    assert penalty == pytest.approx(0.5)


def test_schedule_preference_penalty_is_capped_at_one():
    penalty = schedule_preference_penalty(
        preferred_slot=5,
        proposed_slot=10,
        max_shift_slots=4,
    )

    assert penalty == 1.0


def test_schedule_preference_penalty_handles_zero_max_shift():
    penalty = schedule_preference_penalty(
        preferred_slot=5,
        proposed_slot=6,
        max_shift_slots=0,
    )

    assert penalty == 1.0


def test_schedule_preference_penalty_zero_max_shift_at_preferred_slot():
    penalty = schedule_preference_penalty(
        preferred_slot=5,
        proposed_slot=5,
        max_shift_slots=0,
    )

    assert penalty == 0.0