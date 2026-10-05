from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import settings

client = TestClient(app)


def test_resource_crud_and_validation():
    transformer = {
        "id": "api-tx", "name": "API transformer", "rated_capacity_kw": 100,
        "current_load_kw": 50, "connected_building_ids": [], "safety_margin_pct": 0.1,
    }
    created = client.post("/api/transformers", json=transformer)
    assert created.status_code == 201
    assert created.json()["id"] == "api-tx"
    assert client.get("/api/transformers/api-tx").status_code == 200
    assert client.get("/api/transformers/missing").status_code == 404
    assert client.post("/api/transformers", json={**transformer, "id": "bad", "rated_capacity_kw": -1}).status_code == 422
    assert client.delete("/api/transformers/api-tx").status_code == 200


def test_health_and_comparison_route():
    from app.tests.integration.test_planning_api import _planning_request

    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/api/planning/compare", json=_planning_request())
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["first_strategy"] == "baseline"
    assert payload["second_strategy"] == "optimized"
    assert "baseline_peak_load_kw" in payload["metrics"]


def test_planning_respects_opted_out_occupant():
    from app.tests.integration.test_planning_api import _planning_request

    payload = _planning_request()
    payload["occupants"][0]["opted_out"] = True
    response = client.post("/api/planning/generate", json=payload)
    assert response.status_code == 200, response.text
    protected = [d for d in response.json()["decisions"] if d["building_id"] == "b-001"]
    assert protected
    assert any("OPTED_OUT" in d["reasoning_tags"] for d in protected)


def test_tariff_api_rejects_invalid_slot_and_rate():
    invalid = {"id": "api-tariff-invalid", "name": "bad", "currency": "INR",
               "rate_per_slot": {"96": 2.0}}
    assert client.post("/api/tariffs", json=invalid).status_code == 422
    invalid["rate_per_slot"] = {"4": -1.0}
    assert client.post("/api/tariffs", json=invalid).status_code == 422


def test_persisted_explanations_and_history():
    from app.tests.integration.test_planning_api import _planning_request

    generated = client.post("/api/planning/generate", json=_planning_request())
    assert generated.status_code == 200, generated.text
    result_id = generated.json()["planning_result_id"]
    assert client.get(f"/api/planning/results/{result_id}").status_code == 200
    assert client.get(f"/api/planning/results/{result_id}/explanations").status_code == 200
    assert client.get(f"/api/planning/history/{result_id}").status_code == 200
    assert client.get("/api/planning/results/missing").status_code == 404


def test_emergency_override_endpoint_requires_operator_token(monkeypatch):
    from app.tests.integration.test_planning_api import _planning_request

    monkeypatch.setattr(settings, "OVERRIDE_AUTH_TOKEN", "operator-secret")
    payload = _planning_request()
    payload["emergency_override"] = {
        "operator_id": "operator-1",
        "justification": "Prevent imminent transformer thermal damage",
    }
    response = client.post("/api/planning/emergency-override", json=payload)
    assert response.status_code == 403
