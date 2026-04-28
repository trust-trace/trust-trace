from __future__ import annotations

import logging
import os

import httpx

import eem.config as config

logger = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.1,
) -> str:
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment")

    resolved_model = model or config.EEM_MODEL
    base_url = os.environ.get("OPENROUTER_BASE_URL", _BASE_URL)

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/trust-trace/trust-trace",
                "X-Title": "trust-trace-eem",
            },
            json={
                "model": resolved_model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
