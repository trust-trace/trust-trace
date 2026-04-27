import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "openai/gpt-4o-mini"


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.1,
) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment")

    resolved_model = model or os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
    base_url = os.environ.get("OPENROUTER_BASE_URL", _BASE_URL)
    referer = os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/trust-trace/trust-trace")
    title = os.environ.get("OPENROUTER_X_TITLE", "trust-trace")

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": referer,
                "X-Title": title,
            },
            json={
                "model": resolved_model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
