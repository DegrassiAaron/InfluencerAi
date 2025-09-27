import asyncio
from typing import Any, Dict, Optional

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
    _build_pricing_display,
    _format_pricing_amount,
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


def test_count_tokens_parses_usage_payload() -> None:
    transport = make_transport(
        {
            "/tokenize": httpx.Response(
                200,
                json={
                    "usage": {
                        "prompt_tokens": 7,
                        "completion_tokens": 3,
                        "total_tokens": 10,
                    }
                },
            )
        }
    )

    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            result = await client.count_tokens("demo", "prompt")
        finally:
            await client.close()

        assert result == {
            "prompt_tokens": 7,
            "completion_tokens": 3,
            "total_tokens": 10,
        }

    asyncio.run(scenario())


def test_count_tokens_raises_on_failure_status() -> None:
    transport = make_transport(
        {"/tokenize": httpx.Response(500, json={"error": "boom"})}
    )

    async def scenario() -> None:
        client = OpenRouterClient(transport=transport)

        try:
            with pytest.raises(OpenRouterError):
                await client.count_tokens("demo", "prompt")
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


def test_openrouter_client_reuses_external_httpx_client() -> None:
    captured_headers: dict[str, str] = {}

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as http_client:
            client = OpenRouterClient(api_key="secret-token", client=http_client)

            headers = client._headers()
            captured_headers.update(headers)

            async with client as ctx:
                assert ctx is client

            assert not http_client.is_closed

    asyncio.run(scenario())

    assert captured_headers["Authorization"] == "Bearer secret-token"
    assert captured_headers["Content-Type"] == "application/json"


def test_count_tokens_recovers_from_tokens_list_and_missing_usage_fields() -> None:
    payload = {
        "usage": {
            "prompt_tokens": True,
            "input_tokens": "2",
        },
        "tokens": [1, 2, 3, 4, 5],
    }

    transport = make_transport({"/tokenize": httpx.Response(200, json=payload)})

    async def scenario() -> dict[str, int]:
        client = OpenRouterClient(transport=transport)

        try:
            return await client.count_tokens("demo", "prompt")
        finally:
            await client.close()

    result = asyncio.run(scenario())

    assert result == {
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "total_tokens": 5,
    }


def test_count_tokens_combines_prompt_and_completion_when_total_missing() -> None:
    payload = {
        "usage": {
            "prompt_tokens": "4",
            "completion_tokens": "1",
        },
    }

    transport = make_transport({"/tokenize": httpx.Response(200, json=payload)})

    async def scenario() -> dict[str, int]:
        client = OpenRouterClient(transport=transport)

        try:
            return await client.count_tokens("demo", "prompt")
        finally:
            await client.close()

    result = asyncio.run(scenario())

    assert result == {
        "prompt_tokens": 4,
        "completion_tokens": 1,
        "total_tokens": 5,
    }


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("invalid", None),
        (float("inf"), None),
        ("0.0005", "$0.0005"),
        ("0.05", "$0.05"),
        ("2", "$2"),
    ],
)
def test_format_pricing_amount_handles_various_inputs(value: Any, expected: Optional[str]) -> None:
    assert _format_pricing_amount(value) == expected


def test_build_pricing_display_prefers_prioritized_entries() -> None:
    pricing = {
        "image_generation": {"standard": "   $0.12   "},
        "output": {"text": {"usd": "0.0008"}},
        "misc": {"note": "  "},
    }

    display = _build_pricing_display(pricing)

    assert display == "Output Text Usd: $0.0008"
