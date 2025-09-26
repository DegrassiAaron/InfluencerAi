"""Model presets and helpers for OpenRouter image generation scripts."""

from __future__ import annotations

from typing import Dict

MODEL_PRESETS: Dict[str, str] = {
    "sdxl": "stabilityai/sdxl",
    "sdxl-turbo": "stabilityai/sdxl-turbo",
    "flux": "black-forest-labs/flux-1.1-pro",
    "flux-dev": "black-forest-labs/flux-dev",
    "playground-v25": "playgroundai/playground-v2.5",
    "sdxl-lightning": "luma-photon/stable-diffusion-xl-lightning",
}
"""Mapping between short aliases and full OpenRouter model identifiers."""

MODEL_PRESETS_HELP = ", ".join(f"{alias} → {model}" for alias, model in MODEL_PRESETS.items())
"""Human-readable description of the available aliases."""


def resolve_model_alias(model: str) -> str:
    """Return the full model id for a preset alias, falling back to the original string."""

    alias = model.strip().lower()
    if not alias:
        return model
    return MODEL_PRESETS.get(alias, model.strip())
