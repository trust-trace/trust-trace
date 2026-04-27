"""Text processing helper functions."""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def extract_excerpt(text: str, max_len: int = 300) -> str:
    normalized = normalize_whitespace(text)
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."
