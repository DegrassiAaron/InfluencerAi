"""Unit tests for the OpenRouter client helpers."""
from __future__ import annotations

import unittest
from typing import List

import httpx

from ai_influencer.webapp.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    classify_model_capabilities,
    summarize_models,
)


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._value = start

    def advance(self, delta: float) -> None:
        self._value += delta

    def __call__(self) -> float:
        return self._value


class OpenRouterClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_models_uses_cache_until_ttl_expires(self) -> None:
        calls: List[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            payload = {"data": [{"id": f"model-{len(calls)}"}]}
            return httpx.Response(200, json=payload)

        transport = httpx.MockTransport(handler)
        clock = _FakeClock()
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenRouterClient(
                base_url="https://example.com",
                client=http_client,
                models_ttl=5.0,
                clock=clock,
            )
            first = await client.list_models()
            second = await client.list_models()
            self.assertEqual(first, [{"id": "model-1"}])
            self.assertEqual(second, first)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].headers["Accept"], "application/json")

            clock.advance(10.0)
            third = await client.list_models()

        self.assertEqual(len(calls), 2)
        self.assertEqual(third, [{"id": "model-2"}])

    async def test_generate_text_flattens_chunked_messages(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/chat/completions"):
                body = {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "Hello"},
                                    {"type": "text", "text": ", world!"},
                                ]
                            }
                        }
                    ]
                }
                return httpx.Response(200, json=body)
            raise AssertionError(f"Unexpected URL {request.url}")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenRouterClient(base_url="https://example.com", client=http_client)
            result = await client.generate_text("demo-model", "hi")

        self.assertEqual(result, "Hello, world!")

    async def test_generate_text_raises_for_non_ok(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenRouterClient(base_url="https://example.com", client=http_client)
            with self.assertRaises(OpenRouterError):
                await client.generate_text("demo", "prompt")

    async def test_generate_image_raises_for_non_ok(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="bad request")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenRouterClient(base_url="https://example.com", client=http_client)
            with self.assertRaises(OpenRouterError):
                await client.generate_image(model="demo", prompt="hello")

    async def test_generate_video_returns_payload(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertIn("application/json", request.headers.get("Accept", ""))
            data = {"data": [{"url": "https://video"}]}
            return httpx.Response(200, json=data)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenRouterClient(base_url="https://example.com", client=http_client)
            result = await client.generate_video(model="demo", prompt="hi")

        self.assertEqual(result, {"data": [{"url": "https://video"}]})


class HelperFunctionsTests(unittest.TestCase):
    def test_classify_model_capabilities(self) -> None:
        model = {
            "architecture": {"modality": ["text", "image"]},
            "pricing": {"video": {"prompt": 0.1}},
            "tags": ["beta", None],
        }
        self.assertEqual(
            classify_model_capabilities(model),
            ["beta", "image", "text", "video"],
        )

    def test_summarize_models(self) -> None:
        data = [
            {
                "id": "model-a",
                "name": "Model A",
                "owned_by": "provider",
                "tags": ["image"],
            },
            {"model": "model-b", "pricing": {"image": {"prompt": 0.1}}},
            {"other": "missing id"},
        ]
        summary = summarize_models(data)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["id"], "model-a")
        self.assertEqual(summary[1]["id"], "model-b")
        self.assertIn("image", summary[1]["capabilities"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
