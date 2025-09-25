"""FastAPI application exposing a UI for OpenRouter powered media generation."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .openrouter import (
    OpenRouterClient,
    OpenRouterError,
    summarize_models,
)

app = FastAPI(title="AI Influencer Control Hub")


async def get_client() -> OpenRouterClient:
    return OpenRouterClient()


class TextGenerationRequest(BaseModel):
    model: str = Field(..., description="OpenRouter model identifier")
    prompt: str = Field(..., description="Prompt to send to the model")


class ImageGenerationRequest(BaseModel):
    model: str
    prompt: str
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    width: int = Field(1024, ge=256, le=2048)
    height: int = Field(1024, ge=256, le=2048)
    steps: Optional[int] = Field(None, ge=1, le=100)
    guidance: Optional[float] = Field(None, ge=0.0, le=50.0)


class VideoGenerationRequest(BaseModel):
    model: str
    prompt: str
    duration: Optional[float] = Field(None, ge=1.0, le=60.0)
    size: Optional[str] = Field(None, description="Resolution, e.g. 1024x576")


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/api/models")
async def list_models(client: OpenRouterClient = Depends(get_client)) -> JSONResponse:
    try:
        models = await client.list_models()
    finally:
        await client.close()
    return JSONResponse({"models": summarize_models(models)})


@app.post("/api/generate/text")
async def generate_text(
    payload: TextGenerationRequest,
    client: OpenRouterClient = Depends(get_client),
) -> JSONResponse:
    try:
        result = await client.generate_text(payload.model, payload.prompt)
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()
    return JSONResponse({"content": result})


@app.post("/api/generate/image")
async def generate_image(
    payload: ImageGenerationRequest,
    client: OpenRouterClient = Depends(get_client),
) -> JSONResponse:
    try:
        data = await client.generate_image(
            model=payload.model,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            guidance=payload.guidance,
        )
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()

    blob: Dict[str, Any] = {}
    entries = data.get("data") if isinstance(data, dict) else None
    if isinstance(entries, list) and entries:
        blob = entries[0]
    content: Optional[str] = None
    if isinstance(blob, dict):
        if blob.get("b64_json"):
            content = blob["b64_json"]
        elif blob.get("url"):
            content = blob["url"]
    if not content:
        raise HTTPException(status_code=500, detail="Unexpected image payload")

    # Ensure payload is always base64 encoded for inline display when possible
    if blob.get("b64_json") is None and content.startswith("http"):
        # Do not attempt to inline remote URLs, return as-is
        return JSONResponse({"image": content, "is_remote": True})

    try:
        # Validate base64 formatting for inline display
        base64.b64decode(content)
    except Exception as exc:  # pragma: no cover - defensive path
        raise HTTPException(status_code=500, detail="Invalid image encoding") from exc

    return JSONResponse({"image": content, "is_remote": False})


@app.post("/api/generate/video")
async def generate_video(
    payload: VideoGenerationRequest,
    client: OpenRouterClient = Depends(get_client),
) -> JSONResponse:
    try:
        data = await client.generate_video(
            model=payload.model,
            prompt=payload.prompt,
            duration=payload.duration,
            size=payload.size,
        )
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()

    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise HTTPException(status_code=500, detail="Unexpected video payload")
    blob = entries[0]
    if not isinstance(blob, dict):
        raise HTTPException(status_code=500, detail="Invalid video payload")
    if blob.get("url"):
        return JSONResponse({"video": blob["url"], "is_remote": True})
    if blob.get("b64_json"):
        return JSONResponse({"video": blob["b64_json"], "is_remote": False})
    raise HTTPException(status_code=500, detail="Unsupported video payload")


@app.get("/healthz")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
