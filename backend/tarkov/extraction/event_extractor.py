"""Event extraction module."""

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
from reasoning.collectors.tarkov_collector import TarkovTraceCollector
from reasoning.schemas import TarkovReasoningTrace


class EventExtractor:
    def __init__(self, llm_client=None, event_emitter: Callable | None = None):
        self.keywords = AML_KEYWORDS
        self.llm_client = llm_client
        self.event_emitter = event_emitter

    def extract_events_keyword_based(self, article: ArticleIn) -> tuple[list[EventExtraction], dict[str, TarkovReasoningTrace]]:
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for sentence in split_sentences(article.article.text):
            lowered = sentence.lower()
            for event_type, keywords in self.keywords.items():
                hit = next((kw for kw in keywords if kw in lowered), None)
                if hit:
                    grouped[event_type].append((sentence, hit))

        events: list[EventExtraction] = []
        traces: dict[str, TarkovReasoningTrace] = {}
        
        for event_type, rows in grouped.items():
            collector = TarkovTraceCollector(event_type, getattr(article, "id", None))
            
            sentences = [s for s, _ in rows]
            hits = [k for _, k in rows]
            occurred_at = article.article.published_at or datetime.utcnow()
            source_text = " ".join(sentences[:2])

            # Record keyword extraction
            collector.record_keyword_extraction(
                keywords_searched=self.keywords.get(event_type, []),
                keywords_found=list(set(hits)),
                hit_sentences=sentences,
            )

            # Calculate confidence
            confidence = min(1.0, 0.55 + (0.1 * min(4, len(set(hits)))))
            collector.record_confidence_calculation(
                base_confidence=0.55,
                keyword_count=len(set(hits)),
                keyword_boost=0.1 * min(4, len(set(hits))),
                final_confidence=confidence,
            )

            # Calculate risk level
            risk_level = self.calculate_risk_level(event_type, hits)
            baseline_risk = {
                "money_laundering": 8,
                "fraud": 8,
                "regulatory_action": 6,
                "bankruptcy": 5,
                "sanctions": 9,
                "investigation": 7,
            }.get(event_type, 4)
            boost_value = min(2, max(0, len(set(hits)) - 1))
            collector.record_risk_level(
                baseline_risk=baseline_risk,
                keyword_count=len(set(hits)),
                boost_value=boost_value,
                final_risk_level=risk_level,
            )

            # Record title generation
            generated_title = f"{event_type.replace('_', ' ').title()}: {article.article.title}"[:280]
            collector.record_title_generation(
                article_title=article.article.title,
                generated_title=generated_title,
                template_used=None,
            )

            # Record source reference
            collector.record_source_reference(
                url=article.source.url,
                source_title=article.article.title,
                credibility_score=article.source.credibility_score,
                language=article.article.language,
                published_at=occurred_at,
            )

            source_ref = SourceReference(
                url=article.source.url,
                title=article.article.title,
                source_text=source_text,
                published_at=occurred_at,
                credibility_score=article.source.credibility_score,
                language=article.article.language,
            )

            events.append(
                EventExtraction(
                    event_type=event_type,
                    title=generated_title,
                    description=" ".join(sentences[:3]),
                    risk_level=risk_level,
                    occurred_at=occurred_at,
                    confidence=confidence,
                    source_text=source_text,
                    source_reference=source_ref,
                )
            )
            traces[event_type] = collector.collect()
        
        return events, traces

    def extract_events_llm_based(self, article_text: str, firm_context: str) -> list[EventExtraction]:
        if self.llm_client is None:
            return []
        return self.llm_client.extract_events(article_text, firm_context)

    @staticmethod
    def calculate_risk_level(event_type: str, keywords_found: list[str]) -> int:
        baseline = {
            "money_laundering": 8,
            "fraud": 8,
            "regulatory_action": 6,
            "bankruptcy": 5,
            "sanctions": 9,
            "investigation": 7,
        }.get(event_type, 4)
        boost = min(2, max(0, len(set(keywords_found)) - 1))
        return max(1, min(10, baseline + boost))

    @staticmethod
    def to_event_out(extraction: EventExtraction) -> EventOut:
        return EventOut(
            event_type=extraction.event_type,
            risk_level=extraction.risk_level,
            title=extraction.title,
            occurred_at=extraction.occurred_at,
            confidence=extraction.confidence,
            description=extraction.description,
            source_text=extraction.source_text,
        )

    @staticmethod
    def _build_title(article_title: str, event_type: str) -> str:
        return f"{event_type.replace('_', ' ').title()}: {article_title}"[:280]

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parse_date(value)
        except Exception:
            return None
