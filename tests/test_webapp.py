"""Tests for the FastAPI web application endpoints."""


import pathlib
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_influencer.webapp.openrouter import OpenRouterError, summarize_models


client = TestClient(app, raise_server_exceptions=False)


def test_list_models_returns_summarized_payload_and_closes_client():
    class StubClient:
        def __init__(self) -> None:
            self.close_called = False
            self.models = [
                {
                    "id": "openrouter/model-1",
                    "name": "Model One",
                    "owned_by": "openrouter",
                    "context_length": 8192,
                    "pricing": {"input": "0.0005", "output": "0.001"},
                    "architecture": {"modality": ["text", "image"]},
                },
                {
                    "id": "openrouter/model-2",
                    "name": "Model Two",
                    "owned_by": "openrouter",
                    "pricing": {"video": "0.01"},
                    "tags": ["beta"],
                },
            ]

        async def list_models(self):
            return self.models

        async def close(self):
            self.close_called = True

    stub_client = StubClient()
    app.dependency_overrides[get_client] = lambda: stub_client
    try:
        response = client.get("/api/models")
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 200
    assert response.json() == {"models": summarize_models(stub_client.models)}
    assert stub_client.close_called is True


def test_list_models_handles_openrouter_error_and_closes_client():
    class ErrorStubClient:
        def __init__(self) -> None:
            self.close_called = False

        async def list_models(self):
            raise OpenRouterError("Unable to fetch")

        async def close(self):
            self.close_called = True

    stub_client = ErrorStubClient()
    app.dependency_overrides[get_client] = lambda: stub_client
    try:
        response = client.get("/api/models")
    finally:
        app.dependency_overrides.pop(get_client, None)

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert stub_client.close_called is True


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
