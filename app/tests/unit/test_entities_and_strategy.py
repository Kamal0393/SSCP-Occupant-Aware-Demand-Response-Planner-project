"""
Tests covering:
    - Transformer overload derived properties.
    - Occupant opt-out is a plain, reliable boolean flag.
    - DemandResponseStrategy cannot be instantiated directly (enforces the
      Clean Architecture contract that concrete strategies must implement
      generate_plan and strategy_name).
"""

import pytest

from app.domain.entities.transformer import Transformer
from app.domain.entities.occupant import Occupant
from app.domain.strategies.strategy_interface import DemandResponseStrategy


def test_transformer_overload_detection():
    t = Transformer(id="t1", name="T-1", rated_capacity_kw=100, current_load_kw=120)
    assert t.is_overloaded is True
    assert t.overload_kw == 20


def test_transformer_not_overloaded():
    t = Transformer(id="t2", name="T-2", rated_capacity_kw=100, current_load_kw=80)
    assert t.is_overloaded is False
    assert t.overload_kw == 0


def test_transformer_rejects_invalid_capacity():
    with pytest.raises(ValueError):
        Transformer(id="t3", name="T-3", rated_capacity_kw=0, current_load_kw=10)


def test_occupant_opt_out_flag_defaults_false():
    o = Occupant(id="o1", building_id="b1", display_name="Unit 4B", comfort_range_id="cr1")
    assert o.opted_out is False


def test_occupant_can_opt_out():
    o = Occupant(
        id="o2", building_id="b1", display_name="Unit 4C", comfort_range_id="cr1", opted_out=True
    )
    assert o.opted_out is True


def test_strategy_interface_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DemandResponseStrategy()
