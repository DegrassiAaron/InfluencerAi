"""Tests for the FastAPI web application endpoints."""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from ai_influencer.webapp.main import app, get_client
from ai_influencer.webapp.openrouter import OpenRouterError


client = TestClient(app)


class StubVideoClient:
    """Minimal stub implementing the OpenRouter video client interface."""

    def __init__(self, result=None, error: Optional[Exception] = None):
        self._result = result
        self._error = error
        self.closed = False

    async def generate_video(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._result

    async def close(self):
        self.closed = True


def override_client(client_stub: StubVideoClient) -> None:
    async def _get_client() -> StubVideoClient:
        return client_stub

    app.dependency_overrides[get_client] = _get_client


def reset_overrides() -> None:
    app.dependency_overrides.pop(get_client, None)


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


def test_generate_video_returns_remote_url():
    stub = StubVideoClient({"data": [{"url": "https://cdn.example/video.mp4"}]})
    override_client(stub)
    try:
        response = client.post(
            "/api/generate/video",
            json={"model": "demo/video", "prompt": "A sunny day"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "video": "https://cdn.example/video.mp4",
        "is_remote": True,
    }
    assert stub.closed is True


def test_generate_video_returns_inline_base64_payload():
    stub = StubVideoClient({"data": [{"b64_json": "ZmFrZS12aWRlby1kYXRh"}]})
    override_client(stub)
    try:
        response = client.post(
            "/api/generate/video",
            json={"model": "demo/video", "prompt": "A futuristic city"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "video": "ZmFrZS12aWRlby1kYXRh",
        "is_remote": False,
    }
    assert stub.closed is True


def test_generate_video_missing_entries_returns_error():
    stub = StubVideoClient({"meta": {"usage": "test"}})
    override_client(stub)
    try:
        response = client.post(
            "/api/generate/video",
            json={"model": "demo/video", "prompt": "Missing entries"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 500
    assert response.json() == {"detail": "Unexpected video payload"}
    assert stub.closed is True


def test_generate_video_with_non_dict_blob_returns_error():
    stub = StubVideoClient({"data": ["not-a-dict"]})
    override_client(stub)
    try:
        response = client.post(
            "/api/generate/video",
            json={"model": "demo/video", "prompt": "Invalid entry"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 500
    assert response.json() == {"detail": "Invalid video payload"}
    assert stub.closed is True


def test_generate_video_propagates_openrouter_errors():
    stub = StubVideoClient(error=OpenRouterError("backend unavailable"))
    override_client(stub)
    try:
        response = client.post(
            "/api/generate/video",
            json={"model": "demo/video", "prompt": "Should fail"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 502
    assert response.json() == {"detail": "backend unavailable"}
    assert stub.closed is True
