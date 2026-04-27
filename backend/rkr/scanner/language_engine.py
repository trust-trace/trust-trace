import logging

from ..keywords.risk_keywords import RISK_KEYWORDS
from .regex_engine import RegexEngine

logger = logging.getLogger(__name__)

_STATIC_LANGS = {"en", "pl"}


class LanguageEngineCache:
    """Returns a RegexEngine appropriate for the article language.

    EN and PL use the pre-compiled static engine.
    Any other language triggers an OpenRouter LLM call to generate
    equivalent keywords for that language, then caches the result.
    """

    def __init__(self) -> None:
        self._static_engine = RegexEngine()
        self._cache: dict[str, RegexEngine] = {}

    def get_engine(self, lang: str) -> RegexEngine:
        normalized = (lang or "en").lower()

        if normalized in _STATIC_LANGS:
            return self._static_engine

        if normalized in self._cache:
            return self._cache[normalized]

        extra_keywords = []
        try:
            # Lazy import so tests that never reach a foreign-language article
            # don't require httpx or OPENROUTER_API_KEY.
            from ..llm.keyword_generator import generate_keywords_for_lang

            extra_keywords = generate_keywords_for_lang(normalized)
        except Exception as exc:
            logger.warning(
                "Could not generate LLM keywords for lang=%s: %s — falling back to static",
                normalized,
                exc,
            )

        engine = RegexEngine(keywords=RISK_KEYWORDS + extra_keywords)
        self._cache[normalized] = engine
        return engine
