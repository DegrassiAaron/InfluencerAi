#!/usr/bin/env python3
"""Quick connectivity check against the OpenRouter image generation API."""
from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
import urllib.request

import requests


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY mancante")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "ai-influencer",
    }
    payload = {
        "model": "stability-ai/stable-diffusion-xl-base-1.0",
        "prompt": "portrait photorealistic ai influencer, soft light, 50mm",
        "width": 1024,
        "height": 1024,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/images",
        headers=headers,
        json=payload,
        timeout=180,
    )
    print("HTTP:", response.status_code)
    text = response.text
    print(text[:600])
    if not response.ok:
        sys.exit(1)

    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type:
        print(
            "Unexpected response Content-Type:",
            content_type or "<missing>",
        )
        print("First 400 characters of body:")
        print(text[:400])
        sys.exit(1)

    try:
        data = response.json()
    except (json.JSONDecodeError, requests.exceptions.JSONDecodeError):
        print("Unable to decode JSON response. First 400 characters:")
        print(text[:400])
        sys.exit(1)
    record = (data.get("data") or [{}])[0]

    outdir = pathlib.Path("/workspace/data/synth_openrouter")
    outdir.mkdir(parents=True, exist_ok=True)
    filename = outdir / "test_openrouter.png"

    if "b64_json" in record and record["b64_json"]:
        filename.write_bytes(base64.b64decode(record["b64_json"]))
        print("Saved:", filename)
    elif "url" in record and record["url"]:
        urllib.request.urlretrieve(record["url"], filename)
        print("Saved:", filename)
    else:
        print("Payload inatteso:", json.dumps(data)[:400])


if __name__ == "__main__":
    main()
