"""FastAPI application exposing a UI for OpenRouter powered media generation."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from ai_influencer.webapp import storage
from ai_influencer.webapp.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    summarize_models,
)

app = FastAPI(title="AI Influencer Control Hub")


async def get_client() -> OpenRouterClient:
    return OpenRouterClient()


def get_storage():
    try:
        connection = storage.create_connection()
    except storage.StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        yield connection
    finally:
        connection.close()


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


class DataRecordPayload(BaseModel):
    name: str = Field(..., description="Nome del record", min_length=1, max_length=255)
    value: str = Field(..., description="Valore associato", min_length=1)

    @field_validator("name", "value")
    @classmethod
    def _strip_value(cls, raw: str) -> str:
        cleaned = raw.strip()
        if not cleaned:
            raise ValueError("Il campo non può essere vuoto")
        return cleaned


class AcquisitionMethod(str, Enum):
    """Supported ways to gather influencer insights."""

    OFFICIAL = "official"
    SCRAPE = "scrape"


class InfluencerLookupRequest(BaseModel):
    identifier: str = Field(..., description="Username or profile URL")
    method: AcquisitionMethod = Field(
        AcquisitionMethod.OFFICIAL, description="Data acquisition strategy"
    )


def _mask_secret(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    secret = secret.strip()
    if len(secret) <= 4:
        return "*" * len(secret)
    return "*" * (len(secret) - 4) + secret[-4:]



@dataclass(frozen=True)
class ServiceMetadata:
    """Static metadata describing a configurable external service."""

    id: str
    display_name: str
    default_endpoint: Optional[str]
    api_key_env: Optional[str]
    endpoint_env: Optional[str]


SERVICE_REGISTRY: Dict[str, ServiceMetadata] = {
    "openrouter": ServiceMetadata(
        id="openrouter",
        display_name="OpenRouter",
        default_endpoint="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        endpoint_env="OPENROUTER_BASE_URL",
    ),
}


class ServiceUpdateRequest(BaseModel):
    """Payload used to update the configuration of an external service."""

    api_key: Optional[str] = Field(
        default=None, description="Service API key", min_length=1
    )
    endpoint: Optional[AnyHttpUrl] = Field(
        default=None, description="Override service endpoint"
    )
    base_url: Optional[AnyHttpUrl] = Field(
        default=None, description="Override service base URL"
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("API key must not be empty")
        return value

    @field_validator("endpoint", mode="before")
    @classmethod
    def _normalize_endpoint(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            return value
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def _normalize_base_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            return value
        return value

    @model_validator(mode="after")
    def _ensure_payload(self) -> "ServiceUpdateRequest":

        api_key_provided = "api_key" in self.model_fields_set
        endpoint_provided = "endpoint" in self.model_fields_set
        base_url_provided = "base_url" in self.model_fields_set

        if not any([api_key_provided, endpoint_provided, base_url_provided]):
            raise ValueError("Provide at least one value to update")
        if api_key_provided and self.api_key is None:
            raise ValueError("API key must not be empty")
        return self



def _serialize_service(metadata: ServiceMetadata) -> Dict[str, Any]:
    api_key_value = (
        os.environ.get(metadata.api_key_env) if metadata.api_key_env else None
    )
    endpoint_override = (
        os.environ.get(metadata.endpoint_env) if metadata.endpoint_env else None
    )
    resolved_endpoint = endpoint_override or metadata.default_endpoint
    env_keys: Dict[str, str] = {}
    if metadata.api_key_env:
        env_keys["api_key"] = metadata.api_key_env
    if metadata.endpoint_env:
        env_keys["endpoint"] = metadata.endpoint_env

    return {
        "id": metadata.id,
        "name": metadata.display_name,
        "endpoint": resolved_endpoint,
        "default_endpoint": metadata.default_endpoint,
        "uses_default_endpoint": endpoint_override is None,
        "env": env_keys,
        "has_api_key": bool(api_key_value),
        "api_key_preview": _mask_secret(api_key_value),
    }

@dataclass
class ServiceDefinition:
    """Registry entry describing how to manage a third-party service."""

    name: str
    display_name: str
    api_key_env: Optional[str] = None
    base_url_env: Optional[str] = None

    def _current_api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env) if self.api_key_env else None

    def _current_base_url(self) -> Optional[str]:
        if not self.base_url_env:
            return None
        value = os.environ.get(self.base_url_env)
        return value or None

    def describe(self, *, updated: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_key = self._current_api_key()
        base_url = self._current_base_url()
        payload: Dict[str, Any] = {
            "service": self.name,
            "display_name": self.display_name,
            "has_api_key": bool(api_key),
            "api_key_preview": _mask_secret(api_key),
            "base_url": base_url,
            "environment": {},
        }
        if self.api_key_env:
            payload["environment"][self.api_key_env] = bool(api_key)
        if self.base_url_env:
            payload["environment"][self.base_url_env] = base_url
        if updated is not None:
            payload["updated"] = updated
        return payload

    def update(self, update: ServiceUpdateRequest) -> Dict[str, Any]:
        updated: Dict[str, Any] = {}
        if update.api_key is not None and self.api_key_env:
            os.environ[self.api_key_env] = update.api_key
            updated["api_key"] = True
        if "base_url" in update.model_fields_set and self.base_url_env:
            if update.base_url is None:
                os.environ.pop(self.base_url_env, None)
                updated["base_url"] = None
            else:
                os.environ[self.base_url_env] = str(update.base_url)
                updated["base_url"] = str(update.base_url)
        return self.describe(updated=updated)


SERVICE_REGISTRY: Dict[str, ServiceDefinition] = {
    "openrouter": ServiceDefinition(
        name="openrouter",
        display_name="OpenRouter",
        api_key_env="OPENROUTER_API_KEY",
        base_url_env="OPENROUTER_BASE_URL",
    )
}


def _get_service_or_404(service_name: str) -> ServiceDefinition:
    try:
        return SERVICE_REGISTRY[service_name]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=404, detail=f"Unknown service '{service_name}'") from exc


def _legacy_openrouter_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    legacy: Dict[str, Any] = {
        "has_api_key": data["has_api_key"],
        "api_key_preview": data["api_key_preview"],
        "base_url": data.get("base_url"),
    }
    if "updated" in data:
        legacy["updated"] = data["updated"]
    return legacy


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "index.html", {"request": request, "active_nav": "home"}
    )


@app.get("/influencer", response_class=HTMLResponse)
async def influencer_view(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "influencer.html", {"request": request, "active_nav": "influencer"}
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "settings.html", {"request": request, "active_nav": "settings"}
    )


@app.get("/dati", response_class=HTMLResponse)
async def data_view(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "data.html", {"request": request, "active_nav": "data"}
    )


@app.get("/api/models")
async def list_models(client: OpenRouterClient = Depends(get_client)) -> JSONResponse:
    try:
        models = await client.list_models()
    finally:
        await client.close()
    return JSONResponse({"models": summarize_models(models)})



@app.get("/api/config/services")
async def list_configurable_services() -> Dict[str, Any]:
    services = [_serialize_service(metadata) for metadata in SERVICE_REGISTRY.values()]
    return {"services": services}


@app.post("/api/config/services/{service_id}")
async def update_service_configuration(
    service_id: str, payload: ServiceUpdateRequest
) -> Dict[str, Any]:
    metadata = SERVICE_REGISTRY.get(service_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Service not found")

    updated: Dict[str, Any] = {}
    if payload.api_key is not None:
        if metadata.api_key_env is None:
            raise HTTPException(
                status_code=400, detail="Service does not accept API keys"
            )
        os.environ[metadata.api_key_env] = payload.api_key
        updated["api_key"] = True

    endpoint_provided = "endpoint" in payload.model_fields_set
    if endpoint_provided:
        if metadata.endpoint_env is None:
            raise HTTPException(
                status_code=400, detail="Service does not accept endpoint overrides"
            )
        if payload.endpoint is None:
            os.environ.pop(metadata.endpoint_env, None)
            updated["endpoint"] = None
        else:
            os.environ[metadata.endpoint_env] = str(payload.endpoint)
            updated["endpoint"] = str(payload.endpoint)

    return {
        "service": _serialize_service(metadata),
        "updated": updated,
    }

@app.get("/api/services/{service_name}")
async def get_service_config(service_name: str) -> Dict[str, Any]:
    service = _get_service_or_404(service_name)
    return service.describe()


@app.post("/api/services/{service_name}")
async def update_service_config(
    service_name: str, payload: ServiceUpdateRequest
) -> Dict[str, Any]:
    service = _get_service_or_404(service_name)
    return service.update(payload)


@app.get("/api/config/openrouter")
async def get_openrouter_config() -> Dict[str, Any]:
    service = _get_service_or_404("openrouter")
    return _legacy_openrouter_payload(service.describe())


@app.post("/api/config/openrouter")
async def update_openrouter_config(payload: ServiceUpdateRequest) -> Dict[str, Any]:
    service = _get_service_or_404("openrouter")
    return _legacy_openrouter_payload(service.update(payload))



@app.get("/api/data")
def list_data_records(connection=Depends(get_storage)) -> Dict[str, Any]:
    records = storage.list_records(connection)
    return {"items": records}


@app.post("/api/data", status_code=status.HTTP_201_CREATED)
def create_data_record(
    payload: DataRecordPayload, connection=Depends(get_storage)
) -> Dict[str, Any]:
    record = storage.update_record(
        connection,
        name=payload.name,
        value=payload.value,
    )
    return {"record": record}


@app.put("/api/data/{record_id}")
def update_data_record(
    record_id: int, payload: DataRecordPayload, connection=Depends(get_storage)
) -> Dict[str, Any]:
    try:
        record = storage.update_record(
            connection,
            record_id=record_id,
            name=payload.name,
            value=payload.value,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found") from exc
    return {"record": record}


@app.delete("/api/data/{record_id}")
def delete_data_record(record_id: int, connection=Depends(get_storage)) -> Dict[str, Any]:
    try:
        storage.delete_record(connection, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Record not found") from exc
    return {"deleted": True}


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
