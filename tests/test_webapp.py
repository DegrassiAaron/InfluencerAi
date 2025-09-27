"""Tests for the FastAPI web application endpoints."""

import base64
import os
import pathlib
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import pytest

from ai_influencer.webapp.main import app, get_client
from ai_influencer.webapp.openrouter import OpenRouterError, summarize_models
from ai_influencer.webapp import storage
from ai_influencer.webapp.storage import StorageError


client = TestClient(app, raise_server_exceptions=False)


def test_homepage_renders_index_template():
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/" aria-current="page"' in response.text


def test_influencer_page_renders_influencer_template():
    response = client.get("/influencer")

    assert response.status_code == 200
    assert 'href="/influencer" aria-current="page"' in response.text


def test_settings_page_renders_settings_template():
    response = client.get("/settings")

    assert response.status_code == 200
    assert 'href="/settings" aria-current="page"' in response.text


def test_healthcheck_returns_ok_payload():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture()
def temp_data_db(tmp_path, monkeypatch):
    db_path = tmp_path / "data.sqlite"
    monkeypatch.setenv("DATA_DB_PATH", str(db_path))
    yield db_path
    monkeypatch.delenv("DATA_DB_PATH", raising=False)


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
    payload = response.json()
    assert payload == {"models": summarize_models(stub_client.models)}
    pricing_displays = [model["pricing_display"] for model in payload["models"]]
    assert pricing_displays == ["Output: $0.001", "Video: $0.01"]
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


def test_get_openrouter_config_returns_masked_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123456")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://api.openrouter.ai")

    response = client.get("/api/config/openrouter")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_api_key"] is True
    assert payload["api_key_preview"].endswith("3456")
    assert set(payload["api_key_preview"].replace("3456", "")) == {"*"}
    assert payload["base_url"] == "https://api.openrouter.ai"


def test_get_storage_error_returns_500(monkeypatch):
    original_overrides = dict(app.dependency_overrides)
    original_create_connection = storage.create_connection
    monkeypatch.setattr(
        storage,
        "create_connection",
        lambda: (_ for _ in ()).throw(StorageError("boom")),
    )

    try:
        response = client.get("/api/data")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        setattr(storage, "create_connection", original_create_connection)

    assert response.status_code == 500
    assert "boom" in response.text


def test_update_openrouter_config_updates_environment(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

    response = client.post(
        "/api/config/openrouter",
        json={
            "api_key": "sk-new-9876",
            "base_url": "https://example.com/api/v1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert os.environ["OPENROUTER_API_KEY"] == "sk-new-9876"
    assert os.environ["OPENROUTER_BASE_URL"] == "https://example.com/api/v1"
    assert payload["has_api_key"] is True
    assert payload["api_key_preview"].endswith("9876")
    assert payload["updated"] == {
        "api_key": True,
        "base_url": "https://example.com/api/v1",
    }


def test_update_openrouter_config_allows_base_url_only(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-existing-2222")
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

    response = client.post(
        "/api/config/openrouter", json={"base_url": "https://custom.example/api"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert os.environ["OPENROUTER_API_KEY"] == "sk-existing-2222"
    assert os.environ["OPENROUTER_BASE_URL"] == "https://custom.example/api"
    assert payload["has_api_key"] is True
    assert payload["base_url"] == "https://custom.example/api"
    assert payload["api_key_preview"].endswith("2222")


def test_update_openrouter_config_requires_payload():
    response = client.post("/api/config/openrouter", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Provide at least one value" in err["msg"] for err in detail)


def test_update_openrouter_config_validates_base_url():
    response = client.post(
        "/api/config/openrouter", json={"base_url": "not-a-valid-url"}
    )

    assert response.status_code == 422


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


def test_data_api_returns_empty_collection(temp_data_db):
    response = client.get("/api/data")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_data_api_create_update_and_list(temp_data_db):
    create_response = client.post(
        "/api/data",
        json={"name": "Campagna", "value": "Descrizione iniziale"},
    )

    assert create_response.status_code == 201
    created = create_response.json()["record"]
    assert created["name"] == "Campagna"
    assert created["value"] == "Descrizione iniziale"

    list_response = client.get("/api/data")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]

    update_response = client.put(
        f"/api/data/{created['id']}",
        json={"name": "Campagna", "value": "Aggiornato"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()["record"]
    assert updated["value"] == "Aggiornato"
    assert updated["id"] == created["id"]
    assert updated["updated_at"] != created["updated_at"]


def test_data_api_delete_record(temp_data_db):
    create_response = client.post(
        "/api/data",
        json={"name": "Note", "value": "Da eliminare"},
    )
    assert create_response.status_code == 201
    record_id = create_response.json()["record"]["id"]

    delete_response = client.delete(f"/api/data/{record_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    list_response = client.get("/api/data")
    assert list_response.status_code == 200
    assert list_response.json() == {"items": []}


def test_data_api_handles_missing_record_errors(temp_data_db):
    update_response = client.put(
        "/api/data/999",
        json={"name": "Fantasma", "value": "N/A"},
    )
    assert update_response.status_code == 404
    assert update_response.json() == {"detail": "Record not found"}

    delete_response = client.delete("/api/data/999")
    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "Record not found"}


def test_data_api_validates_payload(temp_data_db):
    response = client.post("/api/data", json={"name": "", "value": ""})

    assert response.status_code == 422


def test_data_html_route_renders(temp_data_db):
    response = client.get("/dati")

    assert response.status_code == 200
    body = response.text
    assert "<table id=\"data-table\"" in body
    assert "data.js" in body


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


@pytest.mark.parametrize("identifier", ["", "   "])
def test_influencer_lookup_requires_identifier(identifier: str) -> None:
    response = client.post(
        "/api/influencer",
        json={"identifier": identifier, "method": "official"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Identifier is required"}


def test_influencer_lookup_normalizes_handle_from_urls() -> None:
    response = client.post(
        "/api/influencer",
        json={
            "identifier": "https://instagram.com/Cool.Creator/",
            "method": "official",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["identifier"] == "Cool.Creator"
    assert payload["profile"]["handle"] == "@Cool.Creator"
    assert payload["profile"]["piattaforma"] == "Instagram"


def test_influencer_lookup_returns_not_found_for_invalid_handles() -> None:
    response = client.post(
        "/api/influencer",
        json={"identifier": "@invalid_creator", "method": "official"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Influencer non trovato"}


@pytest.mark.parametrize(
    "identifier,expected_platform",
    [
        ("@InstaIcon", "Instagram"),
        ("https://www.tiktok.com/@dancewave", "TikTok"),
        ("youtube.com/@visionary", "YouTube"),
        ("emerging_artist", "Generico"),
    ],
)
def test_influencer_lookup_sets_platform_and_metrics_for_scrape_method(
    identifier: str, expected_platform: str
) -> None:
    response = client.post(
        "/api/influencer",
        json={"identifier": identifier, "method": "scrape"},
    )

    assert response.status_code == 200
    payload = response.json()

    profile = payload["profile"]
    metrics = payload["metrics"]

    assert profile["piattaforma"] == expected_platform
    assert profile["fonte_dati"] == "Web scraping"
    assert payload["method"] == "scrape"
    assert profile["handle"].startswith("@")
    assert {"follower", "engagement_rate", "crescita_30g", "media_view"}.issubset(
        metrics.keys()
    )


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
