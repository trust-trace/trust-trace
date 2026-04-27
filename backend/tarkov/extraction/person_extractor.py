"""Person extraction with role proximity heuristics."""

from __future__ import annotations

import re

from tarkov.keywords.aml_keywords import ROLE_KEYWORDS
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import PersonExtraction, SourceReference


NAME_WITH_TITLE_PATTERN = re.compile(r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")
PLAIN_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")


class PersonExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def extract_people(self, article: ArticleIn, event_context: list[str] | None = None) -> list[PersonExtraction]:
        candidates = self.extract_people_keyword_based(article, event_context or [])
        if candidates:
            return candidates
        return self.extract_people_llm_based(article, event_context or [])

    def extract_people_keyword_based(self, article: ArticleIn, event_context: list[str]) -> list[PersonExtraction]:
        text = article.article.text
        lowered = text.lower()
        picks: list[tuple[str, str, str]] = []

        for normalized_role, aliases in ROLE_KEYWORDS.items():
            for role_alias in aliases:
                idx = lowered.find(role_alias.lower())
                if idx < 0:
                    continue
                snippet = text[max(0, idx - 80) : idx + 120].strip()
                for name in self.match_name_patterns(snippet):
                    picks.append((name, normalized_role, snippet))

        dedup: dict[tuple[str, str], PersonExtraction] = {}
        for name, role, snippet in picks:
            key = (name.lower(), role)
            if key in dedup:
                continue
            source_ref = SourceReference(
                url=article.source.url,
                title=article.article.title,
                source_text=snippet,
                published_at=article.article.published_at,
                credibility_score=article.source.credibility_score,
                language=article.article.language,
            )
            dedup[key] = PersonExtraction(
                name=name,
                role=role,
                description=f"Mentioned as {role}",
                confidence=0.7,
                source_text=snippet,
                source_reference=source_ref,
            )
        return list(dedup.values())

    def extract_people_llm_based(self, article: ArticleIn, event_context: list[str]) -> list[PersonExtraction]:
        if self.llm_client is None:
            return []
        return self.llm_client.extract_people(article.article.text, "\n".join(event_context))

    @staticmethod
    def match_name_patterns(text: str) -> list[str]:
        names = [*NAME_WITH_TITLE_PATTERN.findall(text), *PLAIN_NAME_PATTERN.findall(text)]
        out: list[str] = []
        seen: set[str] = set()
        for raw in names:
            cleaned = raw.strip()
            if len(cleaned.split()) < 2:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
        return out
