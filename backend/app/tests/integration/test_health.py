"""
Integration test verifying the FastAPI app boots and the /health endpoint
responds correctly. This is intentionally the only integration test in
Milestone 1 - it exists to catch wiring mistakes (bad imports, middleware
misconfiguration) before we build real endpoints on top of it.
"""

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
