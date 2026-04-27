import json
import logging
import re

from ..keywords.risk_keywords import RISK_KEYWORDS, KeywordDef
from .openrouter_client import chat_completion

logger = logging.getLogger(__name__)

_CATEGORIES: list[tuple[str, float]] = [
    ("terrorism_financing", 1.0),
    ("sanctions", 0.95),
    ("money_laundering", 0.9),
    ("fraud", 0.85),
    ("corruption", 0.8),
    ("regulatory_action", 0.75),
    ("tax_evasion", 0.7),
    ("cybercrime", 0.65),
    ("bankruptcy", 0.6),
]

# Build per-category English example phrases once at import time
_EN_EXAMPLES: dict[str, list[str]] = {}
for _kw in RISK_KEYWORDS:
    if _kw["lang"] == "en":
        _EN_EXAMPLES.setdefault(_kw["category"], []).append(_kw["phrase"])


def _build_prompt(lang: str) -> str:
    lines = []
    for cat, weight in _CATEGORIES:
        examples = _EN_EXAMPLES.get(cat, [])[:4]
        lines.append(f"  - {cat} (weight={weight}): {', '.join(examples)}")
    categories_block = "\n".join(lines)

    return f"""You are an AML (anti-money laundering) expert linguist.

Generate risk keyword phrases in the language with ISO 639-1 code: "{lang}".
These phrases are used to detect financial crimes in news articles written in that language.

Categories with weights and English reference phrases:
{categories_block}

Rules:
- 3-5 phrases per category in the target language "{lang}"
- Use natural expressions from legal and financial journalism in that language
- Include synonyms and common variants
- Do NOT write regex patterns — plain phrases only
- Return ONLY a JSON array, no markdown fences, no explanation

Required JSON format:
[
  {{"phrase": "...", "category": "money_laundering", "weight": 0.9, "lang": "{lang}"}},
  ...
]"""


def generate_keywords_for_lang(lang: str) -> list[KeywordDef]:
    """Call OpenRouter LLM and return KeywordDef list for the given language.

    Returns empty list on any error so the caller can fall back to static keywords.
    """
    prompt = _build_prompt(lang)
    try:
        content = chat_completion(
            [
                {
                    "role": "system",
                    "content": "You are an AML keyword expert. Respond only with a valid JSON array.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        raw: list[dict] = json.loads(content)
        keywords = _parse_response(raw, lang)
        logger.info("LLM generated %d keywords for lang=%s", len(keywords), lang)
        return keywords
    except Exception as exc:
        logger.warning("LLM keyword generation failed for lang=%s: %s", lang, exc)
        return []


def _parse_response(raw: list[dict], lang: str) -> list[KeywordDef]:
    result: list[KeywordDef] = []
    for item in raw:
        try:
            phrase = str(item["phrase"]).strip()
            category = str(item["category"]).strip()
            weight = float(item["weight"])
            if not phrase or category not in {c for c, _ in _CATEGORIES}:
                continue
            # Generate a safe pattern from the phrase rather than trusting the LLM
            pattern = r"\b" + re.escape(phrase) + r"\b"
            result.append(
                KeywordDef(
                    phrase=phrase,
                    pattern=pattern,
                    category=category,
                    weight=weight,
                    lang=lang,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return result
