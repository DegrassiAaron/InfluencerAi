"""Tests for the FastAPI web application endpoints."""

import base64
import pathlib
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from ai_influencer.webapp.main import app, get_client
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


class StubImageClient:
    """Minimal stub implementing the OpenRouter image client interface."""

    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.closed = False
        self.calls: list[dict] = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result

    async def close(self) -> None:
        self.closed = True


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_client, None)


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


def test_generate_image_returns_remote_url_and_closes_client():
    stub_client = StubImageClient(
        result={"data": [{"url": "https://cdn.example.com/image.png"}]}
    )

    async def _override() -> StubImageClient:
        return stub_client

    app.dependency_overrides[get_client] = _override
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub", "prompt": "draw"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "image": "https://cdn.example.com/image.png",
        "is_remote": True,
    }
    assert stub_client.closed is True


def test_generate_image_returns_inline_base64_and_closes_client():
    inline = base64.b64encode(b"pixel").decode()
    stub_client = StubImageClient(result={"data": [{"b64_json": inline}]})

    async def _override() -> StubImageClient:
        return stub_client

    app.dependency_overrides[get_client] = _override
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub", "prompt": "draw"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 200
    assert response.json() == {"image": inline, "is_remote": False}
    assert stub_client.closed is True


def test_generate_image_handles_missing_payload_and_closes_client():
    stub_client = StubImageClient(result={})

    async def _override() -> StubImageClient:
        return stub_client

    app.dependency_overrides[get_client] = _override
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub", "prompt": "draw"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 500
    assert response.json() == {"detail": "Unexpected image payload"}
    assert stub_client.closed is True


def test_generate_image_handles_invalid_base64_and_closes_client():
    stub_client = StubImageClient(
        result={"data": [{"b64_json": "not-base64??"}]}
    )

    async def _override() -> StubImageClient:
        return stub_client

    app.dependency_overrides[get_client] = _override
    try:
        response = client.post(
            "/api/generate/image",
            json={"model": "stub", "prompt": "draw"},
        )
    finally:
        reset_overrides()

    assert response.status_code == 500
    assert response.json() == {"detail": "Invalid image encoding"}
    assert stub_client.closed is True


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
