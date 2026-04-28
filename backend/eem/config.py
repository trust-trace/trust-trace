from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY: str = (
    os.environ.get("EEM_API_KEY") or os.environ.get("LLM_API_KEY", "")
)
EEM_MODEL: str = os.environ.get("EEM_MODEL", "openai/gpt-4o-mini")
EEM_SOURCE_EXCERPT_CHARS: int = int(os.environ.get("EEM_SOURCE_EXCERPT_CHARS", "800"))
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
