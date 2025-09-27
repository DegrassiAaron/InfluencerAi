"""FastAPI application exposing a UI for OpenRouter powered media generation."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from ai_influencer.webapp.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    summarize_models,
)

INFLUENCER_STORE: Dict[str, Dict[str, str]] = {
    "aurora_rise": {
        "story": (
            "Aurora Rise ha iniziato come fotografa itinerante e ora racconta "
            "viaggi spaziali immaginari con un focus su comunità inclusive."
        ),
        "personality": (
            "Ottimista visionaria, parla con tono ispirazionale e calore umano, "
            "invogliando il pubblico a immaginare futuri luminosi."
        ),
    },
    "luca_wave": {
        "story": (
            "Luca Wave è un ex DJ diventato storyteller digitale che mescola "
            "memorie costiere e tecnologia immersiva."
        ),
        "personality": (
            "Rilassato ma curioso, usa un linguaggio poetico e vibrazioni da "
            "tramonto mediterraneo per mettere a proprio agio chi lo segue."
        ),
    },
}


app = FastAPI(title="AI Influencer Control Hub")


async def get_client() -> OpenRouterClient:
    return OpenRouterClient()


def _resolve_influencer_context(
    payload: InfluencerContext,
) -> Tuple[str, str]:
    if payload.story and payload.personality:
        return payload.story, payload.personality

    if payload.influencer_id:
        lookup_key = payload.influencer_id.lower()
        record = INFLUENCER_STORE.get(lookup_key)
        if not record:
            raise HTTPException(status_code=404, detail="Influencer context not found")
        return record["story"], record["personality"]

    raise HTTPException(status_code=422, detail="Contesto influencer mancante")


def _enrich_text_prompt(base_prompt: str, story: str, personality: str) -> str:
    prompt = base_prompt.strip()
    context = (
        f"Storia dell'influencer: {story}\n"
        f"Personalità e tono: {personality}"
    )
    return f"{prompt}\n\n{context}" if prompt else context


def _enrich_visual_prompt(base_prompt: str, story: str, personality: str) -> str:
    prompt = base_prompt.strip()
    visual_context = (
        f"Ispirazione narrativa dalla storia: {story}. "
        f"Tonalità coerente con la personalità: {personality}."
    )
    if not prompt:
        return visual_context
    return (
        f"{prompt}. {visual_context}" if not prompt.endswith(".") else f"{prompt} {visual_context}"
    )


def _enrich_video_prompt(base_prompt: str, story: str, personality: str) -> str:
    prompt = base_prompt.strip()
    video_context = (
        f"Sequenza guidata dalla storia: {story}. "
        f"Atmosfera e voce coerenti con la personalità: {personality}."
    )
    if not prompt:
        return video_context
    return (
        f"{prompt}. {video_context}" if not prompt.endswith(".") else f"{prompt} {video_context}"
    )


class InfluencerContext(BaseModel):
    influencer_id: Optional[str] = Field(
        None,
        description="Identificativo univoco dell'influencer registrato nello store",
    )
    story: Optional[str] = Field(
        None,
        description="Breve storia o background dell'influencer",
    )
    personality: Optional[str] = Field(
        None,
        description="Personalità e tono caratteristico dell'influencer",
    )

    @model_validator(mode="after")
    def validate_context(self) -> "InfluencerContext":
        has_id = bool(self.influencer_id and self.influencer_id.strip())
        has_story = bool(self.story and self.story.strip())
        has_personality = bool(self.personality and self.personality.strip())

        if has_story != has_personality:
            raise ValueError("story e personality devono essere fornite insieme")
        if not has_id and not (has_story and has_personality):
            raise ValueError(
                "specificare influencer_id oppure fornire story e personality"
            )

        if has_id:
            self.influencer_id = self.influencer_id.strip()
        if has_story:
            self.story = self.story.strip()
            self.personality = self.personality.strip()
        return self


class TextGenerationRequest(InfluencerContext):
    model: str = Field(..., description="OpenRouter model identifier")
    prompt: str = Field(..., description="Prompt to send to the model")


class TokenUsageRequest(BaseModel):
    model: str = Field(..., description="OpenRouter model identifier")
    prompt: str = Field(..., description="Prompt to tokenize")


class ImageGenerationRequest(InfluencerContext):
    model: str
    prompt: str
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    width: int = Field(1024, ge=256, le=2048)
    height: int = Field(1024, ge=256, le=2048)
    steps: Optional[int] = Field(None, ge=1, le=100)
    guidance: Optional[float] = Field(None, ge=0.0, le=50.0)


class VideoGenerationRequest(InfluencerContext):
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
        story, personality = _resolve_influencer_context(payload)
        enriched_prompt = _enrich_text_prompt(payload.prompt, story, personality)
        result = await client.generate_text(payload.model, enriched_prompt)
    except HTTPException:
        raise
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()
    return JSONResponse({"content": result})


@app.post("/api/tokenize")
async def count_tokens(
    payload: TokenUsageRequest,
    client: OpenRouterClient = Depends(get_client),
) -> JSONResponse:
    try:
        usage = await client.count_tokens(payload.model, payload.prompt)
    except OpenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await client.close()
    return JSONResponse({"usage": usage})


@app.post("/api/generate/image")
async def generate_image(
    payload: ImageGenerationRequest,
    client: OpenRouterClient = Depends(get_client),
) -> JSONResponse:
    try:
        story, personality = _resolve_influencer_context(payload)
        enriched_prompt = _enrich_visual_prompt(payload.prompt, story, personality)
        data = await client.generate_image(
            model=payload.model,
            prompt=enriched_prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            guidance=payload.guidance,
        )
    except HTTPException:
        raise
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
        story, personality = _resolve_influencer_context(payload)
        enriched_prompt = _enrich_video_prompt(payload.prompt, story, personality)
        data = await client.generate_video(
            model=payload.model,
            prompt=enriched_prompt,
            duration=payload.duration,
            size=payload.size,
        )
    except HTTPException:
        raise
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
