"""
Integration tests for the planning API endpoint.
"""

from fastapi.testclient import TestClient
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
