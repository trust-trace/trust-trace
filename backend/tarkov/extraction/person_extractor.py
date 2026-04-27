"""Person extraction with role proximity heuristics."""

from __future__ import annotations

import re

from tarkov.keywords.aml_keywords import ROLE_KEYWORDS
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import PersonExtraction, SourceReference


NAME_WITH_TITLE_PATTERN = re.compile(r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")
PLAIN_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")

_NAME_STOPWORDS = {
    "agency",
    "bank",
    "board",
    "capital",
    "corp",
    "corporation",
    "company",
    "director",
    "group",
    "holdings",
    "inc",
    "limited",
    "llc",
    "ltd",
    "officer",
    "partner",
    "partners",
    "plc",
    "shareholder",
    "trust",
}


class PersonExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def extract_people(self, article: ArticleIn, event_context: list[str] | None = None) -> list[PersonExtraction]:
        candidates = self.extract_people_keyword_based(article, event_context or [])
        if self.llm_client and getattr(self.llm_client, "has_api_key", False):
            llm_people = self.extract_people_llm_based(article, event_context or [], candidates)
            if llm_people:
                return llm_people
        if candidates:
            return candidates
        return self.extract_people_llm_based(article, event_context or [], [])

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

    def extract_people_llm_based(
        self,
        article: ArticleIn,
        event_context: list[str],
        candidates: list[PersonExtraction],
    ) -> list[PersonExtraction]:
        if self.llm_client is None:
            return []
        if hasattr(self.llm_client, "extract_people_hybrid"):
            raw = self.llm_client.extract_people_hybrid(
                article.article.text,
                "\n".join(event_context),
                [
                    {
                        "name": c.name,
                        "role": c.role,
                        "description": c.description,
                        "confidence": c.confidence,
                        "source_text": c.source_text,
                    }
                    for c in candidates
                ],
            )
            parsed = self._parse_llm_people(article, raw)
            if parsed:
                return parsed
        raw = self.llm_client.extract_people(article.article.text, "\n".join(event_context))
        parsed = self._parse_llm_people(article, raw)
        return parsed

    def _parse_llm_people(self, article: ArticleIn, raw) -> list[PersonExtraction]:
        results: list[PersonExtraction] = []
        seen: set[tuple[str, str]] = set()
        for row in raw if isinstance(raw, list) else []:
            name = str(row.get("name", "")).strip()
            role = str(row.get("role", "")).strip()
            source_text = str(row.get("source_text", "")).strip()
            if not name or not role:
                continue
            key = (name.lower(), role.lower())
            if key in seen:
                continue
            seen.add(key)
            source_ref = SourceReference(
                url=article.source.url,
                title=article.article.title,
                source_text=source_text or article.article.text[:240],
                published_at=article.article.published_at,
                credibility_score=article.source.credibility_score,
                language=article.article.language,
            )
            results.append(
                PersonExtraction(
                    name=name,
                    role=role,
                    description=str(row.get("description", f"Mentioned as {role}")),
                    confidence=float(row.get("confidence", 0.75) or 0.75),
                    source_text=source_text or article.article.text[:240],
                    source_reference=source_ref,
                )
            )
        return results

    @staticmethod
    def match_name_patterns(text: str) -> list[str]:
        names = [*NAME_WITH_TITLE_PATTERN.findall(text)]

        tokens = re.findall(r"\b[A-Z][a-z]+\b", text)
        for left, right in zip(tokens, tokens[1:]):
            names.append(f"{left} {right}")

        out: list[str] = []
        seen: set[str] = set()
        for raw in names:
            cleaned = raw.strip()
            if len(cleaned.split()) < 2:
                continue
            parts = cleaned.lower().split()
            if any(part in _NAME_STOPWORDS for part in parts):
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
        return out
