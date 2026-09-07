import pytest

from app.domain.value_objects.decision import ActionType, Decision


def make_decision(**overrides) -> Decision:
    values = {
        "id": "decision-1",
        "dr_event_id": "event-1",
        "building_id": "building-1",
        "slot_index": 4,
        "action": ActionType.REDUCE_SETPOINT,
        "triggering_constraint": "transformer_overload_hard_limit",
        "objective_weights_used": {
            "peak_reduction": 0.7,
            "comfort": 0.3,
        },
    }
    values.update(overrides)
    return Decision(**values)


def test_action_type_contains_expected_actions():
    assert ActionType.ADJUST_TEMPERATURE.value == "adjust_temperature"
    assert ActionType.DEFER_APPLIANCE.value == "defer_appliance"
    assert ActionType.REDUCE_SETPOINT.value == "reduce_setpoint"
    assert ActionType.NO_ACTION.value == "no_action"
    assert ActionType.OPT_OUT_RESPECTED.value == "opt_out_respected"
    assert ActionType.OVERRIDE_APPLIED.value == "override_applied"


def test_decision_delta_returns_difference():
    decision = make_decision(
        before_value=24.0,
        after_value=22.0,
    )

    assert decision.delta == -2.0


def test_decision_delta_returns_positive_difference_when_value_increases():
    decision = make_decision(
        before_value=20.0,
        after_value=22.0,
    )

    assert decision.delta == 2.0


def test_decision_delta_returns_zero_when_values_are_equal():
    decision = make_decision(
        before_value=22.0,
        after_value=22.0,
    )

    assert decision.delta == 0.0


def test_decision_delta_returns_none_when_before_value_is_missing():
    decision = make_decision(
        before_value=None,
        after_value=22.0,
    )

    assert decision.delta is None


def test_decision_delta_returns_none_when_after_value_is_missing():
    decision = make_decision(
        before_value=24.0,
        after_value=None,
    )

    assert decision.delta is None


def test_decision_defaults_are_applied():
    decision = make_decision()

    assert decision.occupant_id is None
    assert decision.target_variable is None
    assert decision.before_value is None
    assert decision.after_value is None
    assert decision.reasoning_tags == ()
    assert decision.is_override is False
    assert decision.estimated_reduction_kw == 0.0
    assert decision.comfort_score is None


def test_decision_is_immutable():
    decision = make_decision()

    with pytest.raises(AttributeError):
        decision.building_id = "building-2"


def test_decision_preserves_objective_weights_and_reasoning_tags():
    decision = make_decision(
        reasoning_tags=("OVERLOAD_ACTIVE", "WITHIN_COMFORT_RANGE"),
        objective_weights_used={
            "peak_reduction": 0.8,
            "comfort": 0.2,
        },
    )

    assert decision.reasoning_tags == (
        "OVERLOAD_ACTIVE",
        "WITHIN_COMFORT_RANGE",
    )
    assert decision.objective_weights_used == {
        "peak_reduction": 0.8,
        "comfort": 0.2,
    }