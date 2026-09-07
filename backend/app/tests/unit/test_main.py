from fastapi.testclient import TestClient

from app.api.main import app
from app.core.exceptions import MissingTariffDataError


client = TestClient(app)


def test_domain_error_handler_returns_422():
    @app.get("/test-domain-error")
    async def test_domain_error():
        raise MissingTariffDataError("Tariff data unavailable")

    response = client.get("/test-domain-error")

    assert response.status_code == 422

    body = response.json()

    assert body["error_type"] == "MissingTariffDataError"
    assert body["detail"] == "Tariff data unavailable"


def test_unhandled_error_handler_returns_500():
    @app.get("/test-unhandled-error")
    async def test_unhandled_error():
        raise RuntimeError("Internal implementation detail")

    # TestClient normally re-raises server exceptions.
    # This option allows us to inspect our 500 response.
    client_with_no_raise = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client_with_no_raise.get("/test-unhandled-error")

    assert response.status_code == 500

    body = response.json()

    assert body["error_type"] == "InternalServerError"
    assert body["detail"] == "An unexpected error occurred."

    # Internal details must not leak.
    assert "Internal implementation detail" not in response.text