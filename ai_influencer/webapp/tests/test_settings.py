import os
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from ai_influencer.webapp.main import SERVICE_REGISTRY, app


@pytest.fixture(name="client")
def fixture_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for metadata in SERVICE_REGISTRY.values():
        if metadata.api_key_env:
            monkeypatch.delenv(metadata.api_key_env, raising=False)
        if metadata.endpoint_env:
            monkeypatch.delenv(metadata.endpoint_env, raising=False)
    return TestClient(app)


def _get_openrouter_payload(client: TestClient) -> Dict[str, object]:
    response = client.get("/api/config/services")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    services = payload.get("services", [])
    assert services and services[0]["id"] == "openrouter"
    return services[0]


def test_list_services_uses_default_configuration(client: TestClient) -> None:
    service = _get_openrouter_payload(client)
    assert service["endpoint"] == "https://openrouter.ai/api/v1"
    assert service["uses_default_endpoint"] is True
    assert service["has_api_key"] is False
    assert service["api_key_preview"] is None
    assert service["env"] == {
        "api_key": "OPENROUTER_API_KEY",
        "endpoint": "OPENROUTER_BASE_URL",
    }


def test_update_service_persists_api_key_and_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/config/services/openrouter",
        json={
            "api_key": "sk-testvalue",
            "endpoint": "https://example.com/api",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    service = payload["service"]
    assert service["has_api_key"] is True
    assert service["api_key_preview"].endswith("alue")
    assert service["uses_default_endpoint"] is False
    assert service["endpoint"] == "https://example.com/api"
    assert os.environ["OPENROUTER_API_KEY"] == "sk-testvalue"
    assert os.environ["OPENROUTER_BASE_URL"] == "https://example.com/api"

    refreshed = _get_openrouter_payload(client)
    assert refreshed["has_api_key"] is True
    assert refreshed["api_key_preview"].endswith("alue")
    assert refreshed["uses_default_endpoint"] is False
    assert refreshed["endpoint"] == "https://example.com/api"


def test_update_service_allows_clearing_endpoint(client: TestClient) -> None:
    client.post(
        "/api/config/services/openrouter",
        json={"endpoint": "https://example.com/custom"},
    )
    response = client.post(
        "/api/config/services/openrouter",
        json={"endpoint": None},
    )
    assert response.status_code == 200
    payload = response.json()
    service = payload["service"]
    assert service["uses_default_endpoint"] is True
    assert service["endpoint"] == "https://openrouter.ai/api/v1"
    assert "OPENROUTER_BASE_URL" not in os.environ


def test_update_service_rejects_unknown_service(client: TestClient) -> None:
    response = client.post("/api/config/services/unknown", json={"api_key": "x"})
    assert response.status_code == 404


def test_update_service_validates_payload(client: TestClient) -> None:
    response = client.post("/api/config/services/openrouter", json={})
    assert response.status_code == 422

    response = client.post(
        "/api/config/services/openrouter",
        json={"endpoint": "notaurl"},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/config/services/openrouter",
        json={"api_key": ""},
    )
    assert response.status_code == 422
