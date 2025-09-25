"""Async client helpers for interacting with the OpenRouter APIs."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx


class OpenRouterError(RuntimeError):
    """Raised when the OpenRouter API returns a non-successful response."""


class OpenRouterClient:
    """Thin asynchronous wrapper around the OpenRouter REST APIs."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        models_ttl: float = 300.0,
        client: Optional[httpx.AsyncClient] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self._base_url = base_url or os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self._models_ttl = models_ttl
        self._model_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
        self._lock = asyncio.Lock()

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=timeout, transport=transport)
            self._owns_client = True

    async def close(self) -> None:
        if getattr(self, "_owns_client", False):
            await self._client.aclose()
    async def __aenter__(self) -> "OpenRouterClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "AI Influencer WebApp"),
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def list_models(self) -> List[Dict[str, Any]]:
        """Return cached OpenRouter models when possible."""

        async with self._lock:
            now = time.monotonic()
            if (
                self._model_cache is not None
                and now - self._model_cache[0] < self._models_ttl
            ):
                return self._model_cache[1]

            response = await self._client.get(
                f"{self._base_url}/models", headers=self._headers()
            )
            if response.status_code != httpx.codes.OK:
                raise OpenRouterError(
                    f"Unable to fetch models: {response.status_code} {response.text[:200]}"
                )
            data = response.json()
            models: List[Dict[str, Any]] = (
                data.get("data", []) if isinstance(data, dict) else []
            )
            self._model_cache = (now, models)
            return models

    async def generate_text(self, model: str, prompt: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an AI influencer assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        if response.status_code != httpx.codes.OK:
            raise OpenRouterError(
                f"Text generation failed: {response.status_code} {response.text[:200]}"
            )
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise OpenRouterError(f"Unexpected response payload: {data}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            # Some models return tool responses as list chunks
            content = "".join(chunk.get("text", "") for chunk in content)
        if not isinstance(content, str):
            raise OpenRouterError(f"Unsupported message format: {message}")
        return content

    async def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: Optional[int] = None,
        guidance: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if steps is not None:
            payload["steps"] = steps
        if guidance is not None:
            payload["guidance_scale"] = guidance
        response = await self._client.post(
            f"{self._base_url}/images", headers=self._headers(), json=payload
        )
        if response.status_code != httpx.codes.OK:
            raise OpenRouterError(
                f"Image generation failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        duration: Optional[float] = None,
        size: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        if duration is not None:
            payload["duration"] = duration
        if size is not None:
            payload["size"] = size
        response = await self._client.post(
            f"{self._base_url}/videos", headers=self._headers(), json=payload
        )
        if response.status_code != httpx.codes.OK:
            raise OpenRouterError(
                f"Video generation failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()


def classify_model_capabilities(model: Dict[str, Any]) -> List[str]:
    """Infer basic capability tags for a model definition."""

    capabilities: List[str] = []
    architecture = model.get("architecture") or {}
    modality = architecture.get("modality")
    if isinstance(modality, list):
        capabilities.extend(modality)
    elif isinstance(modality, str):
        capabilities.append(modality)

    pricing = model.get("pricing") or {}
    if pricing.get("image") or pricing.get("image_generation"):
        capabilities.append("image")
    if pricing.get("video"):
        capabilities.append("video")
    if pricing.get("input") or pricing.get("output"):
        capabilities.append("text")

    capabilities.extend(model.get("tags", []))
    return sorted({cap.lower() for cap in capabilities if isinstance(cap, str)})


def summarize_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a condensed list of model metadata used by the UI."""

    summary = []
    for item in models:
        model_id = item.get("id") or item.get("model")
        if not model_id:
            continue
        provider = item.get("owned_by") or item.get("organization") or ""
        capabilities = classify_model_capabilities(item)
        summary.append(
            {
                "id": model_id,
                "name": item.get("name") or model_id,
                "provider": provider,
                "capabilities": capabilities,
                "context_length": item.get("context_length"),
                "pricing": item.get("pricing"),
            }
        )
    summary.sort(key=lambda x: x["name"].lower())
    return summary

