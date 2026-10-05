"""
Integration tests for the planning API endpoint.
"""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.api.main import app
from app.core.config import settings
from app.infrastructure.db.models import (
    DecisionModel,
    ExplanationModel,
    PlanningHistoryModel,
    PlanningResultModel,
)
from app.infrastructure.db.session import SessionLocal

client = TestClient(app)


def _planning_request() -> dict:
    return {
        "dr_event": {
            "id": "dr-001",
            "transformer_id": "tx-001",
            "start_time": "2026-09-04T18:00:00",
            "end_time": "2026-09-04T19:00:00",
            "target_reduction_kw": 10.0,
            "status": "planned",
        },
        "transformer": {
            "id": "tx-001",
            "name": "Transformer 1",
            "rated_capacity_kw": 100.0,
            "current_load_kw": 110.0,
            "connected_building_ids": ["b-001", "b-002"],
            "safety_margin_pct": 0.10,
        },
        "buildings": [
            {
                "id": "b-001",
                "name": "Building 1",
                "transformer_id": "tx-001",
                "building_type": "residential",
                "floor_area_sqm": 1000.0,
                "fixed_load_kw": 30.0,
                "flexible_load_kw": 15.0,
                "occupant_ids": ["o-001"],
            },
            {
                "id": "b-002",
                "name": "Building 2",
                "transformer_id": "tx-001",
                "building_type": "commercial",
                "floor_area_sqm": 1500.0,
                "fixed_load_kw": 40.0,
                "flexible_load_kw": 20.0,
                "occupant_ids": ["o-002"],
            },
        ],
        "occupants": [
            {
                "id": "o-001",
                "building_id": "b-001",
                "display_name": "Occupant 1",
                "comfort_range_id": "comfort-001",
                "opted_out": False,
                "allow_override": False,
            },
            {
                "id": "o-002",
                "building_id": "b-002",
                "display_name": "Occupant 2",
                "comfort_range_id": "comfort-001",
                "opted_out": False,
                "allow_override": False,
            },
        ],
        "comfort_ranges": {
            "comfort-001": {
                "id": "comfort-001",
                "variable": "temperature",
                "min_value": 20.0,
                "max_value": 24.0,
                "preferred_value": 22.0,
            }
        },
        "tariff": None,
        "objective_weights": {
            "peak_reduction": 0.5,
            "comfort": 0.5,
        },
    }


def test_generate_plan_returns_decisions():
    response = client.post(
        "/api/planning/generate",
        json=_planning_request(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "decisions" in body
    assert len(body["decisions"]) == 2


def test_generate_plan_meets_target_reduction():
    response = client.post(
        "/api/planning/generate",
        json=_planning_request(),
    )

    assert response.status_code == 200

    decisions = response.json()["decisions"]

    total_reduction = sum(
        decision["estimated_reduction_kw"]
        for decision in decisions
    )

    assert total_reduction == 10.0


def test_generate_plan_returns_execution_metrics_and_explanations():
    response = client.post("/api/planning/generate", json=_planning_request())
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["baseline_peak_load_kw"] == 110.0
    assert body["metrics"]["optimized_peak_load_kw"] == 100.0
    assert body["metrics"]["peak_reduction_kw"] == 10.0
    assert body["metrics"]["baseline_energy_kwh"] == 110.0
    assert body["metrics"]["optimized_energy_kwh"] == 100.0
    assert body["metrics"]["modified_decision_count"] > 0
    assert all(decision["explanation"] for decision in body["decisions"])
    result_id = body["planning_result_id"]
    with SessionLocal() as session:
        assert session.get(PlanningResultModel, result_id) is not None
        persisted_decisions = session.scalars(select(DecisionModel).where(
            DecisionModel.planning_result_id == result_id)).all()
        persisted_explanations = session.scalars(select(ExplanationModel).where(
            ExplanationModel.decision_id.in_([decision.id for decision in persisted_decisions]))).all()
        assert len(persisted_decisions) == len(body["decisions"])
        assert len(persisted_explanations) == len(body["decisions"])


def test_emergency_override_rejects_missing_operator_token(monkeypatch):
    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "configured-secret")
    request = _planning_request()
    request["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    request["occupants"][0]["opted_out"] = True
    request["occupants"][0]["allow_override"] = True
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 422
    assert response.json()["error_type"] == "UnauthorizedOverrideError"


def test_emergency_override_with_valid_token_is_recorded(monkeypatch):
    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "configured-secret")
    request = _planning_request()
    request["transformer"]["rated_capacity_kw"] = 95.0
    request["dr_event"]["status"] = "active"
    request["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    request["occupants"][0]["opted_out"] = True
    request["occupants"][0]["allow_override"] = True
    response = client.post("/api/planning/generate", json=request,
                           headers={"X-Override-Token": "configured-secret"})
    assert response.status_code == 200
    override = response.json()["override"]
    assert override["requested"] is True
    assert override["authorized"] is True
    assert override["applied"] is True
    assert override["affected_building_ids"] == ["b-001"]
    assert "authorized emergency action" in override["explanation"]
    overridden = [decision for decision in response.json()["decisions"] if decision["is_override"]]
    assert overridden
    assert "OVERRIDE_OPERATOR:operator-1" in overridden[0]["reasoning_tags"]
    result_id = response.json()["planning_result_id"]
    with SessionLocal() as session:
        history = session.scalars(select(PlanningHistoryModel).where(
            PlanningHistoryModel.planning_result_id == result_id,
            PlanningHistoryModel.action == "emergency_override_applied",
        )).all()
        assert history
        assert history[0].actor == "operator-1"
        assert history[0].details["justification"] == "Prevent imminent transformer thermal damage"


def test_missing_tariff_rejects_incomplete_supplied_rates():
    request = _planning_request()
    request["tariff"] = {
        "id": "partial-tariff", "name": "Partial", "currency": "INR",
        "rate_per_slot": {72: 10.0},
    }
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 422
    assert response.json()["error_type"] == "MissingTariffDataError"
    assert "no rate defined" in response.json()["detail"]


def test_occupancy_sensor_failure_stops_planning():
    request = _planning_request()
    request["occupancy_sensor_status"] = "failed"
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 422
    assert response.json()["error_type"] == "OccupancySensorFailureError"
    assert "planning was not run" in response.json()["detail"]


def test_insufficient_capacity_is_reported_as_solver_infeasibility():
    request = _planning_request()
    for occupant in request["occupants"]:
        occupant["opted_out"] = True
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["infeasible"] is True
    assert any("INFEASIBLE_REQUEST" in decision["reasoning_tags"]
               for decision in body["decisions"])
    assert all(decision["estimated_reduction_kw"] == 0
               for decision in body["decisions"])


def test_unauthorized_override_returns_forbidden_on_override_route(monkeypatch):
    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "configured-secret")
    request = _planning_request()
    request["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    response = client.post("/api/planning/emergency-override", json=request)
    assert response.status_code == 403
    assert response.json()["error_type"] == "UnauthorizedOverrideError"


def test_override_rejects_invalid_operator_or_justification():
    request = _planning_request()
    request["emergency_override"] = {
        "operator_id": "   ",
        "justification": "          ",
    }
    response = client.post("/api/planning/emergency-override", json=request)
    assert response.status_code == 422
    assert "emergency_override" in response.text


def test_override_requires_occupant_consent_even_with_valid_operator_token(monkeypatch):
    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "configured-secret")
    request = _planning_request()
    request["transformer"]["rated_capacity_kw"] = 95.0
    request["dr_event"]["status"] = "active"
    request["occupants"][0]["opted_out"] = True
    request["occupants"][0]["allow_override"] = False
    request["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    response = client.post("/api/planning/emergency-override", json=request,
                           headers={"X-Override-Token": "configured-secret"})
    assert response.status_code == 403
    assert response.json()["error_type"] == "UnauthorizedOverrideError"
    assert "consented" in response.json()["detail"]


def test_override_does_not_bypass_comfort_hard_bounds(monkeypatch):
    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "configured-secret")
    request = _planning_request()
    request["transformer"]["rated_capacity_kw"] = 108.5
    request["dr_event"]["status"] = "active"
    request["dr_event"]["target_reduction_kw"] = 1.5
    request["comfort_ranges"]["comfort-001"]["max_value"] = 22.2
    request["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    request["occupants"][0]["opted_out"] = True
    request["occupants"][0]["allow_override"] = True
    response = client.post("/api/planning/emergency-override", json=request,
                           headers={"X-Override-Token": "configured-secret"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["override"]["applied"] is True
    overridden = next(d for d in body["decisions"] if d["building_id"] == "b-001")
    assert overridden["is_override"] is True
    assert "WITHIN_HARD_COMFORT_BOUNDS" in overridden["reasoning_tags"]
    assert 0.0 <= overridden["comfort_score"] <= 1.0


def test_planning_response_exposes_weighted_cost_and_comfort_metrics():
    request = _planning_request()
    request["tariff"] = {
        "id": "full-tariff", "name": "Flat", "currency": "INR",
        "rate_per_slot": {slot: 10.0 for slot in range(96)},
    }
    request["objective_weights"] = {
        "peak_reduction": 0.5, "comfort": 0.4, "cost_weight": 0.6,
    }
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["comfort_metric"] is not None
    assert metrics["cost_metric"] is not None
    assert metrics["comfort_weight"] == 0.4
    assert metrics["cost_weight"] == 0.6
    assert metrics["stakeholder_objective_value"] == pytest.approx(
        0.4 * (1 - metrics["comfort_metric"]) + 0.6 * metrics["cost_metric"]
    )


def test_planning_response_uses_default_stakeholder_weights():
    request = _planning_request()
    request.pop("objective_weights")
    request["tariff"] = {
        "id": "full-tariff-default", "name": "Flat", "currency": "INR",
        "rate_per_slot": {slot: 10.0 for slot in range(96)},
    }
    response = client.post("/api/planning/generate", json=request)
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["comfort_weight"] == 0.5
    assert metrics["cost_weight"] == 0.25
