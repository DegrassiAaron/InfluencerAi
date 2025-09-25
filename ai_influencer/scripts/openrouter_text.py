#!/usr/bin/env python3
"""Generate storyboard, script and caption seeds using OpenRouter chat models.

The previous pipeline relied on Leonardo.ai for both text prompts and
image generation.  This module replaces the text generation portion with
an OpenRouter-first approach: it queries an OpenRouter-hosted large
language model and persists the returned structured data locally so that
the downstream steps (captioning, TTS metadata, etc.) can continue to
operate unchanged.

Example usage::

    export OPENROUTER_API_KEY=sk-or-v1-...
    python3 scripts/openrouter_text.py \
        --prompt_bank scripts/prompt_bank.yaml \
        --out data/text/storyboard.json

"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

import requests
import yaml


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


SYSTEM_PROMPT = (
    "You are an experienced creative director for short-form social media "
    "videos.  Given persona details and creative levers you must produce a "
    "concise storyboard, a spoken script and at least 5 caption seeds.  "
    "Return strict JSON with the following schema: {\"storyboard\": [" 
    "{\"scene\": str, \"beats\": [str]}], \"script\": str, "
    "\"caption_seeds\": [str]}"
)


def call_openrouter(model: str, messages: list[dict[str, str]], max_tokens: int = 600) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Set OPENROUTER_API_KEY environment variable")

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # The following headers are recommended by OpenRouter for rate-limit fairness.
        "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://localhost"),
        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "AI Influencer Pipeline"),
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "messages": messages,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Malformed response from OpenRouter: {data}") from exc


def build_prompt(persona: str, prompt_bank: Dict[str, Any]) -> str:
    scenes = prompt_bank.get("scenes", [])
    lighting = prompt_bank.get("lighting", [])
    poses = prompt_bank.get("poses", [])
    outfits = prompt_bank.get("outfits", [])
    focals = prompt_bank.get("focals", [])

    return (
        "You are provided with persona and stylistic controls for an AI influencer.\n" \
        f"Persona: {persona}\n" \
        f"Scene presets: {scenes}\n" \
        f"Lighting options: {lighting}\n" \
        f"Poses: {poses}\n" \
        f"Outfits: {outfits}\n" \
        f"Focal lengths: {focals}.\n" \
        "Create a storyboard of 4-6 scenes referencing the presets, a 90-second "
        "script aligned with the storyboard, and concise caption seeds suitable "
        "for social media (10-15 words each)."
    )


def save_json(data: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate storyboard/script using OpenRouter")
    parser.add_argument("--prompt_bank", required=True, help="YAML file with persona and style levers")
    parser.add_argument("--model", default="meta-llama/llama-3.1-70b-instruct", help="OpenRouter chat model ID")
    parser.add_argument("--out", required=True, help="Destination JSON file")
    args = parser.parse_args()

    with open(args.prompt_bank, "r", encoding="utf-8") as f:
        prompt_bank = yaml.safe_load(f)

    persona = prompt_bank.get("persona", "AI influencer")
    user_prompt = build_prompt(persona, prompt_bank)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = call_openrouter(args.model, messages)

    try:
        parsed: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "The OpenRouter response was not valid JSON. "
            "Adjust the prompt or inspect the raw output."
        ) from exc

    save_json(parsed, Path(args.out))
    print(f"Saved OpenRouter text plan to {args.out}")


if __name__ == "__main__":
    main()

