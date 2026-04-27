"""Event extraction logic (keyword + optional LLM)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Callable

from dateutil.parser import parse as parse_date

from tarkov.keywords.aml_keywords import AML_KEYWORDS
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.event import EventOut
from tarkov.schemas.parsed_result import EventExtraction, SourceReference
from tarkov.utils.text_utils import split_sentences


class EventExtractor:
    def __init__(self, llm_client=None, event_emitter: Callable | None = None):
        self.keywords = AML_KEYWORDS
        self.llm_client = llm_client
        self.event_emitter = event_emitter

    def extract_events_keyword_based(self, article: ArticleIn) -> list[EventExtraction]:
        text = article.article.text
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        sentences = split_sentences(text)

        for sentence in sentences:
            lowered = sentence.lower()
            for event_type, keywords in self.keywords.items():
                for keyword in keywords:
                    if keyword in lowered:
                        grouped[event_type].append((sentence, keyword))
                        break

        extracted: list[EventExtraction] = []
        for event_type, hits in grouped.items():
            sentences_for_type = [s for s, _ in hits]
            keywords = [k for _, k in hits]
            title = self._build_title(article.article.title, event_type)
            source_text = " ".join(sentences_for_type[:2])
            occurred_at = article.article.published_at or datetime.utcnow()
            risk_level = self.calculate_risk_level(event_type, keywords)
            confidence = min(1.0, 0.55 + (0.1 * min(4, len(keywords))))
            source_reference = SourceReference(
                url=article.source.url,
                title=article.article.title,
                source_text=source_text,
                published_at=occurred_at,
                credibility_score=article.source.credibility_score,
                language=article.article.language,
            )

            extracted.append(
                EventExtraction(
                    event_type=event_type,
                    title=title,
                    description=" ".join(sentences_for_type[:3]),
                    risk_level=risk_level,
                    occurred_at=occurred_at,
                    confidence=confidence,
                    source_text=source_text,
                    source_reference=source_reference,
                )
            )

        return extracted

    def extract_events_llm_based(self, article_text: str, firm_context: str) -> list[EventExtraction]:
        if self.llm_client is None:
            return []
        return self.llm_client.extract_events(article_text, firm_context)

    def calculate_risk_level(self, event_type: str, keywords_found: list[str]) -> int:
        base = {
            "money_laundering": 8,
            "fraud": 8,
            "regulatory_action": 6,
            "bankruptcy": 5,
            "sanctions": 9,
            "investigation": 7,
        }.get(event_type, 4)
        boost = min(2, max(0, len(set(keywords_found)) - 1))
        return max(1, min(10, base + boost))

    def to_event_out(self, extraction: EventExtraction) -> EventOut:
        return EventOut(
            event_type=extraction.event_type,
            risk_level=extraction.risk_level,
            title=extraction.title,
            occurred_at=extraction.occurred_at,
            confidence=extraction.confidence,
            description=extraction.description,
            source_text=extraction.source_text,
        )

    def _build_title(self, article_title: str, event_type: str) -> str:
        event_label = event_type.replace("_", " ").title()
        return f"{event_label}: {article_title}"[:280]

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return parse_date(value)
        except Exception:
            return None
