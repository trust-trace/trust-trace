"""Async OpenRouter HTTP client for TrustWeb LLM calls."""

from __future__ import annotations

import json
import logging

import httpx

from trust_web.config import TrustWebConfig

logger = logging.getLogger(__name__)


async def chat_completion(
    messages: list[dict[str, str]],
    config: TrustWebConfig,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 800,
) -> str:
    """Send a chat completion request to OpenRouter. Returns the content string."""
    if not config.llm_api_key:
        logger.warning(
            "⚠️  No LLM API key configured — skipping LLM call. "
            "Set TRUSTWEB_LLM_API_KEY env var to enable LLM-powered edge discovery and explanations."
        )
        return ""

    use_model = model or config.llm_model
    url = f"{config.openrouter_base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.openrouter_http_referer,
        "X-Title": config.openrouter_x_title,
    }
    payload = {
        "model": use_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""
    except Exception:
        logger.exception("LLM call failed (model=%s)", use_model)
        return ""


def parse_json_response(text: str) -> dict | list | None:
    """Extract JSON from LLM response, tolerating markdown fences and truncation."""
    if not text:
        return None
    cleaned = text.strip()

    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try parsing as-is
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Handle truncated JSON arrays: find all complete objects in a partial array
    if cleaned.startswith("["):
        try:
            # Try to close the array by finding the last complete object
            last_brace = cleaned.rfind("}")
            if last_brace > 0:
                truncated = cleaned[:last_brace + 1] + "]"
                result = json.loads(truncated)
                logger.info("Recovered %d items from truncated JSON array", len(result))
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse LLM JSON: %s...", cleaned[:200])
    return None
