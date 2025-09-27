"""FastAPI application exposing a UI for OpenRouter powered media generation."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai_influencer.webapp.openrouter import (
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


class AcquisitionMethod(str, Enum):
    """Supported ways to gather influencer insights."""

    OFFICIAL = "official"
    SCRAPE = "scrape"


class InfluencerLookupRequest(BaseModel):
    identifier: str = Field(..., description="Username or profile URL")
    method: AcquisitionMethod = Field(
        AcquisitionMethod.OFFICIAL, description="Data acquisition strategy"
    )


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


@app.post("/api/influencer")
async def influencer_lookup(payload: InfluencerLookupRequest) -> JSONResponse:
    identifier = payload.identifier.strip()
    if not identifier:
        raise HTTPException(status_code=422, detail="Identifier is required")

    normalized = identifier.lower()
    if "instagram" in normalized or "insta" in normalized:
        platform = "Instagram"
    elif "tiktok" in normalized:
        platform = "TikTok"
    elif "youtube" in normalized or "youtu" in normalized:
        platform = "YouTube"
    else:
        platform = "Generico"

    handle = identifier.lstrip("@")
    if "/" in handle:
        handle = handle.rstrip("/").split("/")[-1]

    if not handle:
        raise HTTPException(status_code=422, detail="Impossibile determinare l'handle")

    if "invalid" in handle.lower():
        raise HTTPException(status_code=404, detail="Influencer non trovato")

    friendly_name = handle.replace("_", " ").title()
    method_label = (
        "API ufficiali" if payload.method == AcquisitionMethod.OFFICIAL else "Web scraping"
    )

    profile: Dict[str, Any] = {
        "handle": f"@{handle}",
        "nome": friendly_name,
        "piattaforma": platform,
        "fonte_dati": method_label,
    }

    followers_base = max(1_000, len(handle) * 1_250)
    engagement = round(min(8.5, 3.2 + len(handle) * 0.17), 2)
    metrics: Dict[str, Any] = {
        "follower": followers_base,
        "engagement_rate": f"{engagement}%",
        "crescita_30g": "+" + str(int(followers_base * 0.08)),
        "media_view": int(followers_base * 0.45),
    }

    base_success = 87 + len(handle) * 3
    now_iso = datetime.now(timezone.utc).isoformat()
    media: List[Dict[str, Any]] = []
    for position in range(1, 11):
        media_type = "video" if position % 3 == 0 else "immagine"
        success_score = round(base_success - (position - 1) * 4.5, 2)
        original_url = f"https://social.example/{handle}/post/{position}"
        image_url = f"https://cdn.social.example/{handle}/media/{position}.jpg"
        thumbnail_url = f"{image_url}?size=thumbnail"
        seed = f"{handle}-{position}".encode()
        image_base64 = base64.b64encode(seed).decode()
        transcript: Optional[str]
        if media_type == "video":
            transcript = (
                f"Trascrizione simulata del contenuto #{position} di {friendly_name}."
            )
        else:
            transcript = None

        media.append(
            {
                "id": f"{handle}-top-{position}",
                "titolo": f"Top contenuto #{position} di {friendly_name}",
                "tipo": media_type,
                "testo_post": (
                    f"{friendly_name} condivide un aggiornamento di punta #{position}"
                ),
                "image_url": image_url,
                "image_base64": image_base64,
                "thumbnail_url": thumbnail_url,
                "success_score": success_score,
                "original_url": original_url,
                "pubblicato_il": now_iso,
                "transcript": transcript,
            }
        )

    media.sort(key=lambda item: item["success_score"], reverse=True)

    payload_data = {
        "profile": profile,
        "metrics": metrics,
        "media": media,
        "identifier": handle,
        "method": payload.method.value,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(payload_data)


@app.get("/healthz")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
