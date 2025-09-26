"""Tests for the FastAPI web application endpoints."""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_influencer.webapp.main import app, get_client
from ai_influencer.webapp.openrouter import OpenRouterError


client = TestClient(app)


class StubTextClient:
    """Minimal async client stub for exercising the text generation route."""

    def __init__(self, *, result: str = "stub-response", error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.closed = False
        self.calls: list[tuple[str, str]] = []

    async def generate_text(self, model: str, prompt: str) -> str:
        self.calls.append((model, prompt))
        if self._error:
            raise self._error
        return self._result

    async def close(self) -> None:
        self.closed = True


def _clear_overrides() -> None:
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


def test_generate_text_uses_stubbed_client_and_closes() -> None:
    stub = StubTextClient(result="expected text")

    async def override_client() -> StubTextClient:
        return stub

    app.dependency_overrides[get_client] = override_client

    response = client.post(
        "/api/generate/text",
        json={"model": "meta/llama", "prompt": "Hello"},
    )

    try:
        assert response.status_code == 200
        assert response.json() == {"content": "expected text"}
        assert stub.calls == [("meta/llama", "Hello")]
        assert stub.closed is True
    finally:
        _clear_overrides()


def test_generate_text_returns_502_on_openrouter_error() -> None:
    stub = StubTextClient(error=OpenRouterError("stub failure"))

    async def override_client() -> StubTextClient:
        return stub

    app.dependency_overrides[get_client] = override_client

    response = client.post(
        "/api/generate/text",
        json={"model": "meta/llama", "prompt": "Hello"},
    )

    try:
        assert response.status_code == 502
        assert response.json() == {"detail": "stub failure"}
        assert stub.closed is True
    finally:
        _clear_overrides()
