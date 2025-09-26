import asyncio
from typing import Any, Dict

import pathlib
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_influencer.scripts.openrouter_models import MODEL_PRESETS, resolve_model_alias
from ai_influencer.webapp.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    classify_model_capabilities,
    summarize_models,
)


def make_transport(route_map: Dict[str, httpx.Response]) -> httpx.AsyncBaseTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        for path, response in route_map.items():
            if request.url.path.endswith(path):
                return response
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_list_models_caches_within_ttl() -> None:
    call_count = 0

    async def scenario() -> None:
        nonlocal call_count

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"data": [{"id": "model-a"}]})

        transport = httpx.MockTransport(handler)
        client = OpenRouterClient(models_ttl=60, transport=transport)

        try:
            first = await client.list_models()
            second = await client.list_models()
        finally:
            await client.close()

        assert call_count == 1
        assert first == second == [{"id": "model-a"}]

    asyncio.run(scenario())


def test_list_models_refreshes_after_ttl_expiry() -> None:
    call_count = 0

    async def scenario() -> None:
        nonlocal call_count

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"data": [{"id": f"model-{call_count}"}]})

        transport = httpx.MockTransport(handler)
        client = OpenRouterClient(models_ttl=0, transport=transport)

        try:
            first = await client.list_models()
            await asyncio.sleep(0)
            second = await client.list_models()
        finally:
            await client.close()

        assert call_count == 2
        assert first != second

    asyncio.run(scenario())


def test_list_models_raises_on_failure_status() -> None:
    transport = make_transport({"/models": httpx.Response(500, json={"error": "boom"})})

    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            with pytest.raises(OpenRouterError):
                await client.list_models()
        finally:
            await client.close()

    asyncio.run(scenario())


def test_generate_text_supports_chunked_content() -> None:
    transport = make_transport(
        {
            "/chat/completions": httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"text": "part one "},
                                    {"text": "and two"},
                                ]
                            }
                        }
                    ]
                },
            )
        }
    )
    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            output = await client.generate_text("demo", "prompt")
        finally:
            await client.close()

        assert output == "part one and two"

    asyncio.run(scenario())


def test_generate_text_raises_on_failure_status() -> None:
    transport = make_transport(
        {
            "/chat/completions": httpx.Response(500, json={"error": "boom"})
        }
    )
    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            with pytest.raises(OpenRouterError):
                await client.generate_text("demo", "prompt")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_generate_image_returns_payload() -> None:
    payload = {"data": [{"url": "http://example/image.png"}]}
    transport = make_transport({"/images": httpx.Response(200, json=payload)})
    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            response = await client.generate_image(model="demo", prompt="hi")
        finally:
            await client.close()

        assert response == payload

    asyncio.run(scenario())


def test_generate_image_raises_on_failure_status() -> None:
    transport = make_transport({"/images": httpx.Response(500, json={"error": "boom"})})

    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            with pytest.raises(OpenRouterError):
                await client.generate_image(model="demo", prompt="hi")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_generate_video_raises_on_failure_status() -> None:
    transport = make_transport({"/videos": httpx.Response(500, json={"error": "boom"})})

    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            with pytest.raises(OpenRouterError):
                await client.generate_video(model="demo", prompt="hi")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_classify_model_capabilities_collects_unique_tags() -> None:
    model = {
        "architecture": {"modality": ["text", "image"]},
        "pricing": {"video": 0.01, "image": 0.02},
        "tags": ["Text", "custom"],
    }

    result = classify_model_capabilities(model)

    assert result == ["custom", "image", "text", "video"]


def test_summarize_models_orders_by_name() -> None:
    models: list[dict[str, Any]] = [
        {"id": "beta", "name": "Beta", "tags": []},
        {"id": "alpha", "name": "Alpha", "tags": []},
    ]

    summary = summarize_models(models)

    assert [item["id"] for item in summary] == ["alpha", "beta"]


def test_resolve_model_alias_is_case_insensitive() -> None:
    assert resolve_model_alias("SDXL") == MODEL_PRESETS["sdxl"]


def test_resolve_model_alias_passthrough_for_custom_ids() -> None:
    custom = "my-org/custom-model"
    assert resolve_model_alias(custom) == custom
