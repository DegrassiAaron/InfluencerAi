#!/usr/bin/env python3
"""Batch image generation using the OpenRouter Images API.

The original tooling downloaded renders from Leonardo.ai.  This
replacement keeps the surrounding dataset/QC pipeline intact while
swapping the backend for OpenRouter-hosted diffusion models (e.g. SDXL,
Flux, etc.).  Prompts are produced from the same YAML prompt bank to
preserve creative direction.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import requests
import yaml

from ai_influencer.scripts.openrouter_models import (
    MODEL_PRESETS_HELP,
    resolve_model_alias,
)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def request_image(model: str, prompt: str, negative_prompt: str | None, size: str) -> Dict[str, Any]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Set OPENROUTER_API_KEY environment variable")

    url = f"{OPENROUTER_BASE_URL}/images"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://localhost"),
        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "AI Influencer Pipeline"),
    }
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def extract_image_bytes(response: Dict[str, Any]) -> bytes:
    data = response.get("data")
    if not data:
        raise RuntimeError(f"No image data returned: {response}")
    blob = data[0]
    if "b64_json" in blob:
        return base64.b64decode(blob["b64_json"])
    if "url" in blob:
        download = requests.get(blob["url"], timeout=120)
        download.raise_for_status()
        return download.content
    raise RuntimeError(f"Unsupported image payload: {blob}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images via OpenRouter Images API")
    parser.add_argument("--prompt_bank", required=True, help="YAML prompt bank with persona/scenes")
    parser.add_argument("--out", required=True, help="Output directory for generated images")
    parser.add_argument(
        "--model",
        default="sdxl",
        help=(
            "OpenRouter image model ID. Preset alias disponibili: "
            f"{MODEL_PRESETS_HELP}."
        ),
    )
    parser.add_argument("--size", default="1024x1024", help="Image resolution, e.g. 1024x1024")
    parser.add_argument("--per_scene", type=int, default=12, help="Images to sample per scene preset")
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds to wait between requests")
    args = parser.parse_args()

    with open(args.prompt_bank, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    model_id = resolve_model_alias(args.model)
    if model_id != args.model:
        print(f"[openrouter] alias '{args.model}' risolto in '{model_id}'")

    persona: str = cfg.get("persona", "AI influencer")
    negatives: str = cfg.get("negatives", "")
    scenes = cfg.get("scenes", [])
    lighting = cfg.get("lighting", [])
    poses = cfg.get("poses", [])
    outfits = cfg.get("outfits", [])
    focals = cfg.get("focals", [])

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {}

    for scene in scenes:
        for idx in range(args.per_scene):
            pose = poses[idx % len(poses)] if poses else ""
            outfit = outfits[idx % len(outfits)] if outfits else ""
            focal = focals[idx % len(focals)] if focals else ""
            light = lighting[idx % len(lighting)] if lighting else ""
            prompt = (
                f"{persona}\n"
                f"Scene: {scene}\n"
                f"Pose: {pose}\n"
                f"Outfit: {outfit}\n"
                f"Lighting: {light}\n"
                f"Optics: {focal}, shallow depth of field, photo-realistic, 8k render."
            )

            try:
                response = request_image(model_id, prompt, negatives, args.size)
                image_bytes = extract_image_bytes(response)
                name = sha(prompt + str(idx))
                out_file = out_dir / f"{name}.png"
                with out_file.open("wb") as f:
                    f.write(image_bytes)
                manifest[name] = {
                    "scene": scene,
                    "pose": pose,
                    "outfit": outfit,
                    "focal": focal,
                    "lighting": light,
                    "prompt": prompt,
                    "model": model_id,
                    "size": args.size,
                }
                print(f"[openrouter] saved {out_file}")
            except Exception as exc:
                print(f"[error] {exc}")

            time.sleep(max(args.sleep, 0.0))

    manifest_path = out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()

