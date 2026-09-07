from app.application.services.explanation_service import ExplanationService
from app.domain.value_objects.decision import ActionType, Decision


def make_decision(**overrides) -> Decision:
    values = {
        "id": "D1",
        "dr_event_id": "DR1",
        "building_id": "B1",
        "slot_index": 4,
        "action": ActionType.REDUCE_SETPOINT,
        "triggering_constraint": "transformer_overload_hard_limit",
        "objective_weights_used": {
            "peak_reduction": 0.8,
            "comfort": 0.2,
        },
        "before_value": 4.0,
        "after_value": 2.0,
        "estimated_reduction_kw": 2.0,
        "comfort_score": 0.8,
    }
    values.update(overrides)
    return Decision(**values)


def test_explains_reduction_decision():
    service = ExplanationService()

    explanation = service.explain(make_decision())

    assert "B1" in explanation
    assert "2.0 kW" in explanation
    assert "transformer_overload_hard_limit" in explanation


def test_explains_no_action_decision():
    service = ExplanationService()

    explanation = service.explain(
        make_decision(
            action=ActionType.NO_ACTION,
            before_value=None,
            after_value=None,
            estimated_reduction_kw=0.0,
        )
    )

    assert "B1" in explanation
    assert "no action" in explanation.lower()
def test_explains_reasoning_tags():
    service = ExplanationService()

    explanation = service.explain(
        make_decision(
            reasoning_tags=("OVERLOAD_ACTIVE", "WITHIN_COMFORT_RANGE"),
        )
    )

    assert "OVERLOAD_ACTIVE" in explanation
    assert "WITHIN_COMFORT_RANGE" in explanation    
def test_explains_objective_weights():
    service = ExplanationService()

    explanation = service.explain(
        make_decision(
            objective_weights_used={
                "peak_reduction": 0.8,
                "comfort": 0.2,
            }
        )
    )

    assert "peak_reduction=0.8" in explanation
    assert "comfort=0.2" in explanation
def test_explains_override_decision():
    service = ExplanationService()

    explanation = service.explain(
        make_decision(
            action=ActionType.OVERRIDE_APPLIED,
            is_override=True,
        )
    )

    assert "override" in explanation.lower()
def test_explains_opt_out_respected():
    service = ExplanationService()

    explanation = service.explain(
        make_decision(
            action=ActionType.OPT_OUT_RESPECTED,
            estimated_reduction_kw=0.0,
            triggering_constraint="occupant_opt_out",
            reasoning_tags=("OPTED_OUT",),
        )
    )

    assert "opt-out was respected" in explanation.lower()
    assert "OPTED_OUT" in explanation