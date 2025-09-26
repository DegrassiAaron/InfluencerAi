# Implementing OpenRouter client features

Follow these steps to add the OpenRouter client utilities required by the test suite.

1. **Locate the module**  
   Open `ai_influencer/webapp/openrouter.py`.  Search for the module docstring `"""Async client helpers for interacting with the OpenRouter APIs."""` to quickly find the file.

2. **Define the error type**  
   Near the top of the file, add a custom exception class `OpenRouterError(RuntimeError)` so failures from the API can be raised consistently.

3. **Implement `OpenRouterClient.__init__`**  
   In the `OpenRouterClient` class, configure the async HTTP client.  Accept optional keyword arguments for `api_key`, `base_url`, `timeout`, `models_ttl`, `client`, and `transport`.  When `client` is `None`, construct a new `httpx.AsyncClient` using the provided `timeout` and optional `transport`, and record whether the client is owned by the wrapper.  Initialise an asyncio lock (`asyncio.Lock()`) and store a `clock` callable (default `time.monotonic`) for cache invalidation.

4. **Add context-manager helpers**  
   Implement `close()`, `__aenter__`, and `__aexit__` so that the wrapper can be used in `async with` blocks.  Only close the underlying client when it was created by `OpenRouterClient` (`self._owns_client` flag).

5. **Build the header helper**  
   Create a `_headers()` method returning the JSON headers required by OpenRouter.  Always include `Content-Type`, `Accept`, `HTTP-Referer`, and `X-Title`.  If an API key is available, add an `Authorization: Bearer <key>` header.

6. **Implement model caching in `list_models`**  
   Inside `list_models`, acquire `self._lock` before reading or updating the cache (`self._model_cache`).  Check whether the cached timestamp is still within `models_ttl` seconds of the current `clock()` value, and if so, return the cached list.  Otherwise, perform a GET request to `{self._base_url}/models`.  On non-200 statuses, raise `OpenRouterError`.  Parse the JSON payload and extract `data` (default to `[]` if missing or malformed).  Update the cache tuple with `(timestamp, models)` before returning it.

7. **Handle chunked chat content in `generate_text`**  
   POST to `{self._base_url}/chat/completions` with a system/user message array.  After verifying a 200 status, load the JSON and extract the first choice’s `message`.  If `message["content"]` is a list, join each chunk’s `text` field; otherwise ensure it is a string.  Raise `OpenRouterError` on missing choices or unexpected structures.

8. **Return raw payload from `generate_image` and `generate_video`**  
   For image and video generation, POST to `/images` or `/videos` respectively with the provided keyword arguments.  Include optional fields (`negative_prompt`, `steps`, `guidance_scale`, `duration`, `size`) only when supplied.  Raise `OpenRouterError` on non-200 responses and return `response.json()` on success.

9. **Implement capability classification**  
   Create `classify_model_capabilities(model: Dict[str, Any]) -> List[str]`.  Collect modality values from `model["architecture"]["modality"]`, convert any strings to lowercase, and extend with pricing-derived tags (`"image"`, `"video"`, `"text"`) and existing `tags`.  Return a sorted list of unique lowercase strings.

10. **Summarise models for the UI**  
    Implement `summarize_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]`.  For each item, pull the identifier from `id` or `model`, derive `provider` from `owned_by` or `organization`, compute capabilities via `classify_model_capabilities`, and collect `context_length`/`pricing`.  Append dictionaries with these fields and finally sort the summary list by the lowercase display `name`.

11. **Run the test suite**  
    Execute `pytest tests/test_openrouter.py` to confirm the implementation satisfies the expected behaviour for caching, chunked responses, error handling, and summarisation.
