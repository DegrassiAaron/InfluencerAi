# Implementing OpenRouter client enhancements

Follow these steps to implement the OpenRouter client behaviour expected by the FastAPI webapp and its pytest suite.

## 1. Update the async client wrapper
1. Open `ai_influencer/webapp/openrouter.py` and locate the `class OpenRouterClient` definition (search for `class OpenRouterClient`).
2. In `__init__`, make sure the constructor accepts optional `api_key`, `base_url`, `timeout`, `models_ttl`, `client`, `transport`, and `clock` parameters. Initialise `self._client` with `httpx.AsyncClient(timeout=timeout, transport=transport)` when a client is not passed in, and store a TTL cache tuple `self._model_cache` plus an `asyncio.Lock` for cache coordination.
3. In `list_models`, wrap the body in `async with self._lock:`. Use the injected `clock` function to read the current time and return cached results while `now - cached_ts < self._models_ttl`. When the cache is stale, perform a `GET` against `f"{self._base_url}/models"` with `_headers()`, raise an `OpenRouterError` when `response.status_code` is not `httpx.codes.OK`, and cache the parsed `data["data"]` payload.
4. Update `_headers()` so it always sends `Content-Type`, `Accept`, `HTTP-Referer`, and `X-Title`. When `self._api_key` is truthy, add the `Authorization: Bearer …` header.

## 2. Support chunked chat completions
1. Still in `ai_influencer/webapp/openrouter.py`, locate `async def generate_text`.
2. Build the request payload with a fixed system prompt (`"You are an AI influencer assistant."`) and the caller-supplied prompt. POST it to `"/chat/completions"` using `_headers()`.
3. After validating the HTTP status code, parse the JSON. Accept both string content and the chunked format returned by tool-calling models (a list where each element exposes `chunk.get("text", "")`). Concatenate chunk text into a single string. Raise `OpenRouterError` when the message payload is missing or malformed.

## 3. Surface raw image/video responses
1. In `generate_image`, construct the JSON payload using the supplied parameters (`model`, `prompt`, `negative_prompt`, `width`, `height`, `steps`, `guidance`). POST to `"/images"`, raise `OpenRouterError` on non-200 responses, and return `response.json()`.
2. In `generate_video`, build a payload with `model`, `prompt`, and optional `duration`/`size`. POST to `"/videos"`, raise errors on non-200 responses, and return `response.json()`.

## 4. Classify model capabilities
1. Locate `def classify_model_capabilities` in the same module.
2. Collect modalities from `model["architecture"]["modality"]`, supporting both lists and single strings.
3. Inspect `model["pricing"]` for non-zero `image`/`image_generation`, `video`, `input`, or `output` fields to append `"image"`, `"video"`, and `"text"` tags.
4. Extend the capability list with any custom `model["tags"]`. Lowercase every string capability, drop non-string entries, and return a sorted, de-duplicated list.

## 5. Summarise models for the UI
1. In `def summarize_models`, iterate over the `models` list and pull out the `id` (falling back to `model`), provider (`owned_by` or `organization`), capabilities (via `classify_model_capabilities`), context length, and pricing data.
2. Skip entries without an identifier. Build dictionaries containing `id`, `name` (fallback to the identifier), `provider`, `capabilities`, `context_length`, and `pricing`.
3. Sort the resulting list case-insensitively by the `name` field before returning it.

## 6. FastAPI integration checks
1. Open `ai_influencer/webapp/main.py` and ensure each endpoint (`/api/models`, `/api/generate/text`, `/api/generate/image`, `/api/generate/video`, `/api/influencer`) relies on `OpenRouterClient` for backend calls and translates responses exactly as expected by `tests/test_webapp.py` (search for `@app.post("/api/influencer")`).
2. For `/api/generate/image`, validate base64 payloads and return `{"image": content, "is_remote": False}` for inline blobs or `{"image": url, "is_remote": True}` when the API only returns a remote URL.
3. For `/api/generate/video`, require a `data` list and accept either URL or base64 fields, translating them to the JSON shape consumed by the frontend/tests.
4. `/api/influencer` should normalise the identifier, detect the platform (Instagram/TikTok/YouTube/Generico), generate fake metrics and media items (10 entries sorted by `success_score`), and return metadata fields validated by the pytest assertions.

## 7. Verification
Run the test suite from the project root to confirm the implementation:
```bash
pytest -q
```
