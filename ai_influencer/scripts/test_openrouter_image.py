#!/usr/bin/env python3
"""Quick connectivity check against the OpenRouter image generation API."""
from __future__ import annotations

import base64
import json
import logging
import os
import pathlib
import sys
import urllib.request

import requests


def _configure_logger(outdir: pathlib.Path) -> logging.Logger:
    logger = logging.getLogger("test_openrouter")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(outdir / "test_openrouter.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY mancante")

    outdir = pathlib.Path("/workspace/data/synth_openrouter")
    outdir.mkdir(parents=True, exist_ok=True)
    logger = _configure_logger(outdir)

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
    logger.info("HTTP status: %s", response.status_code)
    text = response.text
    logger.info("First 600 characters of body: %s", text[:600])
    if not response.ok:
        sys.exit(1)

    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type:
        codex/fix-python3-command-not-found-error-jhqsca
        logger.error(
            "Unexpected response Content-Type: %s", content_type or "<missing>"
        )
        logger.error("First 400 characters of body: %s", text[:400])
        print(
            "Unexpected response Content-Type:",
            content_type or "<missing>",
        )
        print("First 400 characters of body:")
        print(text[:400])
        main
        sys.exit(1)

    try:
        data = response.json()
    except (json.JSONDecodeError, requests.exceptions.JSONDecodeError):
        codex/fix-python3-command-not-found-error-jhqsca
        logger.exception(
            "Unable to decode JSON response. First 400 characters: %s", text[:400]
        )
        print("Unable to decode JSON response. First 400 characters:")
        print(text[:400])
        main
        sys.exit(1)
    record = (data.get("data") or [{}])[0]

    filename = outdir / "test_openrouter.png"

    if "b64_json" in record and record["b64_json"]:
        filename.write_bytes(base64.b64decode(record["b64_json"]))
        logger.info("Saved image to %s", filename)
    elif "url" in record and record["url"]:
        urllib.request.urlretrieve(record["url"], filename)
        logger.info("Downloaded image to %s", filename)
    else:
        logger.error("Payload inatteso: %s", json.dumps(data)[:400])


if __name__ == "__main__":
    main()
