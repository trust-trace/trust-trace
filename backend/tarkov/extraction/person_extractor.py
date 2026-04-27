"""Person extraction logic."""

from __future__ import annotations

import re

from tarkov.keywords.aml_keywords import ROLE_KEYWORDS
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import PersonExtraction, SourceReference


NAME_WITH_TITLE_PATTERN = re.compile(
    r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
)

PLAIN_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")


class PersonExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def extract_people(self, article: ArticleIn, event_context: list[str] | None = None) -> list[PersonExtraction]:
        keyword_people = self.extract_people_keyword_based(article, event_context or [])
        if keyword_people:
            return keyword_people
        return self.extract_people_llm_based(article, event_context or [])

    def extract_people_keyword_based(self, article: ArticleIn, event_context: list[str]) -> list[PersonExtraction]:
        text = article.article.text
        lowered = text.lower()
        candidates: list[tuple[str, str, str]] = []

        for normalized_role, role_variants in ROLE_KEYWORDS.items():
            for role_variant in role_variants:
                idx = lowered.find(role_variant.lower())
                if idx == -1:
                    continue
                snippet = text[max(0, idx - 80) : idx + 120]
                names = self.match_name_patterns(snippet)
                for name in names:
                    candidates.append((name, normalized_role, snippet.strip()))

        dedup: dict[tuple[str, str], PersonExtraction] = {}
        for name, role, snippet in candidates:
            key = (name.lower(), role)
            if key in dedup:
                continue
            source_reference = SourceReference(
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
                description=f"Mentioned as {role} in article context",
                confidence=0.7,
                source_text=snippet,
                source_reference=source_reference,
            )

        return list(dedup.values())

    def extract_people_llm_based(self, article: ArticleIn, event_context: list[str]) -> list[PersonExtraction]:
        if self.llm_client is None:
            return []
        return self.llm_client.extract_people(article.article.text, "\n".join(event_context))

    def match_name_patterns(self, text: str) -> list[str]:
        title_hits = NAME_WITH_TITLE_PATTERN.findall(text)
        plain_hits = PLAIN_NAME_PATTERN.findall(text)
        names = [n.strip() for n in title_hits + plain_hits]
        result: list[str] = []
        seen = set()
        for name in names:
            if len(name.split()) < 2:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(name)
        return result
