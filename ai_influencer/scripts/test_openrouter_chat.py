#!/usr/bin/env python3
"""Quick connectivity check against the OpenRouter chat completions API."""
from __future__ import annotations

import os
import sys

import requests


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY mancante")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "ai-influencer",
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "scrivi: ok"}],
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    print("HTTP:", response.status_code)
    print(response.text[:600])


if __name__ == "__main__":
    main()
