"""Common text normalization helpers."""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def extract_excerpt(text: str, max_len: int = 300) -> str:
    normalized = normalize_whitespace(text)
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."
