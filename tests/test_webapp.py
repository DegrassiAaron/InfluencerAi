"""Tests for the FastAPI web application endpoints."""

import base64
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from ai_influencer.webapp.main import app, get_client
from ai_influencer.webapp.openrouter import OpenRouterError


client = TestClient(app)


class StubImageClient:
    """Test double providing controlled responses for image generation."""

    def __init__(self, payload: Dict[str, Any] | None = None, error: Exception | None = None):
        self._payload = payload or {}
        self._error = error
        self.closed = False

    async def generate_image(self, **_: Any) -> Dict[str, Any]:
        if self._error:
            raise self._error
        return self._payload

    async def close(self) -> None:
        self.closed = True


def test_influencer_lookup_returns_enriched_media():
    response = client.post(
        "/api/influencer",
        json={"identifier": "@socialstar", "method": "official"},
    )

    assert response.status_code == 200
    payload = response.json()

    media = payload["media"]
    assert len(media) == 10

    success_scores = [item["success_score"] for item in media]
    assert success_scores == sorted(success_scores, reverse=True)

    for item in media:
        assert item["id"].startswith("socialstar-top-")
        assert item["titolo"]
        assert item["testo_post"]
        assert item["original_url"].startswith("https://")
        assert item["thumbnail_url"].startswith("https://")
        assert item["image_url"].startswith("https://")
        assert isinstance(item["image_base64"], str)
        assert "success_score" in item
        assert "pubblicato_il" in item
        assert "transcript" in item


def test_generate_image_returns_inline_base64_payload():
    inline_image = base64.b64encode(b"demo-image").decode()
    stub = StubImageClient(payload={"data": [{"b64_json": inline_image}]})
    app.dependency_overrides[get_client] = lambda: stub
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub-model", "prompt": "render inline"},
        )
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"image": inline_image, "is_remote": False}
    assert stub.closed is True


def test_generate_image_returns_remote_url_payload():
    remote_url = "https://example.com/image.png"
    stub = StubImageClient(payload={"data": [{"url": remote_url}]})
    app.dependency_overrides[get_client] = lambda: stub
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub-model", "prompt": "render remote"},
        )
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"image": remote_url, "is_remote": True}
    assert stub.closed is True


def test_generate_image_missing_keys_triggers_server_error():
    stub = StubImageClient(payload={"data": [{}]})
    app.dependency_overrides[get_client] = lambda: stub
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub-model", "prompt": "bad payload"},
        )
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"] == "Unexpected image payload"
    assert stub.closed is True


def test_generate_image_surfaces_openrouter_errors():
    error = OpenRouterError("temporary upstream failure")
    stub = StubImageClient(error=error)
    app.dependency_overrides[get_client] = lambda: stub
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub-model", "prompt": "will fail"},
        )
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"] == "temporary upstream failure"
    assert stub.closed is True
