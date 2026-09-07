"""
Integration tests for the planning API endpoint.
"""

from fastapi.testclient import TestClient

from app.api.main import app

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