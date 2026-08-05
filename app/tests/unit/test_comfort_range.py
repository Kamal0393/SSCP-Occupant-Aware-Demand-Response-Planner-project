"""
Tests for domain.value_objects.comfort_range.ComfortRange.

Purpose: verify hard-bound validation at construction time and the soft
comfort scoring function used by both the soft-constraint penalty and the
UI's "Comfort indicator".
"""

import pytest

from app.domain.value_objects.comfort_range import ComfortRange


def test_valid_comfort_range_constructs():
    cr = ComfortRange(id="cr1", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    assert cr.preferred_value == 21


def test_rejects_min_greater_than_or_equal_max():
    with pytest.raises(ValueError):
        ComfortRange(id="cr2", variable="temperature_c", min_value=24, max_value=19, preferred_value=21)


def test_rejects_preferred_value_outside_bounds():
    with pytest.raises(ValueError):
        ComfortRange(id="cr3", variable="temperature_c", min_value=19, max_value=24, preferred_value=30)


def test_is_within_hard_bounds():
    cr = ComfortRange(id="cr4", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    assert cr.is_within_hard_bounds(19) is True
    assert cr.is_within_hard_bounds(24) is True
    assert cr.is_within_hard_bounds(18.9) is False
    assert cr.is_within_hard_bounds(24.1) is False


def test_comfort_score_at_preferred_value_is_one():
    cr = ComfortRange(id="cr5", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    assert cr.comfort_score(21) == 1.0


def test_comfort_score_outside_bounds_is_zero():
    cr = ComfortRange(id="cr6", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    assert cr.comfort_score(30) == 0.0
    assert cr.comfort_score(10) == 0.0


def test_comfort_score_decreases_with_distance_from_preferred():
    cr = ComfortRange(id="cr7", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    near = cr.comfort_score(22)
    far = cr.comfort_score(23.5)
    assert 0.0 < far < near < 1.0


def test_comfort_score_is_zero_exactly_at_hard_bound():
    # Documented behaviour: score hits 0 exactly AT a hard bound, not just beyond it.
    cr = ComfortRange(id="cr8", variable="temperature_c", min_value=19, max_value=24, preferred_value=21)
    assert cr.comfort_score(24) == 0.0
    assert cr.comfort_score(19) == 0.0
