"""Heuristic connection extraction for Tarkov."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
import re

from tarkov.schemas.article import ArticleIn
from tarkov.schemas.event import EventOut
from tarkov.schemas.parsed_result import (
    EventExtraction,
    PersonExtraction,
    SourceReference,
)


_DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_DATACLASS_KWARGS)
class ConnectionExtraction:
    connection_type: str
    entity_1_type: str
    entity_1_id: str
    entity_1_name: str | None
    entity_2_type: str
    entity_2_id: str
    entity_2_name: str | None
    relationship_description: str | None
    confidence: float | None = None
    intensity: float | None = None


class ConnectionExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def extract_connections(
        self,
        article: ArticleIn,
        company_names: list[str],
        people: list[PersonExtraction],
        events: list[EventExtraction],
    ) -> list[ConnectionExtraction]:
        heuristic = []
        heuristic.extend(self.extract_business_relationships(article, company_names))
        heuristic.extend(self.extract_shared_directors(article, people))
        heuristic.extend(self.extract_activity_links(article, events))

        if self.llm_client and getattr(self.llm_client, "has_api_key", False):
            raw = self.llm_client.extract_connections_hybrid(
                article.article.text,
                company_names,
                [p.name for p in people],
                [e.description for e in events],
            )
            parsed = self._parse_llm_connections(raw)
            if parsed:
                return parsed

        return heuristic

    def extract_business_relationships(self, article: ArticleIn, firm_names: list[str]):
        text = article.article.text.lower()
        hits = [name for name in firm_names if name.lower() in text]
        if len(hits) < 2:
            return []

        first, second = hits[0], hits[1]
        return [
            ConnectionExtraction(
                connection_type="business_relationship",
                entity_1_type="company",
                entity_1_id=first,
                entity_1_name=first,
                entity_2_type="company",
                entity_2_id=second,
                entity_2_name=second,
                relationship_description="Companies co-mentioned in a business context",
                confidence=0.65,
                intensity=0.65,
            )
        ]

    def _parse_llm_connections(self, raw) -> list[ConnectionExtraction]:
        results: list[ConnectionExtraction] = []
        seen: set[tuple[str, str, str]] = set()
        for row in raw if isinstance(raw, list) else []:
            connection_type = str(row.get("connection_type", "")).strip()
            entity_1_name = str(row.get("entity_1_name", "")).strip()
            entity_2_name = str(row.get("entity_2_name", "")).strip()
            entity_1_type = (
                str(row.get("entity_1_type", "company")).strip() or "company"
            )
            entity_2_type = (
                str(row.get("entity_2_type", "company")).strip() or "company"
            )
            if not connection_type or not entity_1_name or not entity_2_name:
                continue
            key = (connection_type, entity_1_name.lower(), entity_2_name.lower())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                ConnectionExtraction(
                    connection_type=connection_type,
                    entity_1_type=entity_1_type,
                    entity_1_id=str(row.get("entity_1_id", entity_1_name)),
                    entity_1_name=entity_1_name,
                    entity_2_type=entity_2_type,
                    entity_2_id=str(row.get("entity_2_id", entity_2_name)),
                    entity_2_name=entity_2_name,
                    relationship_description=str(
                        row.get("relationship_description", "")
                    ).strip()
                    or None,
                    confidence=float(row.get("confidence", 0.6) or 0.6),
                    intensity=float(
                        row.get("intensity", row.get("confidence", 0.6)) or 0.6
                    ),
                )
            )
        return results

    def extract_shared_directors(
        self, article: ArticleIn, people: list[PersonExtraction]
    ):
        text = article.article.text
        firms = self._find_firms(text)
        if not firms:
            return []

        first_firm = firms[0]
        connections: list[ConnectionExtraction] = []
        for person in people:
            if person.role and person.role.lower() in {
                "director",
                "ceo",
                "cfo",
                "officer",
                "manager",
            }:
                connections.append(
                    ConnectionExtraction(
                        connection_type="shared_director",
                        entity_1_type="company",
                        entity_1_id=first_firm,
                        entity_1_name=first_firm,
                        entity_2_type="person",
                        entity_2_id=person.name,
                        entity_2_name=person.name,
                        relationship_description=f"{person.name} is mentioned as {person.role}",
                        confidence=person.confidence,
                        intensity=person.confidence,
                    )
                )
        return connections

    def extract_activity_links(self, article: ArticleIn, events: list[EventExtraction]):
        text = article.article.text
        firms = self._find_firms(text)
        if len(firms) < 2 or not events:
            return []

        first, second = firms[0], firms[1]
        return [
            ConnectionExtraction(
                connection_type="activity_link",
                entity_1_type="company",
                entity_1_id=first,
                entity_1_name=first,
                entity_2_type="company",
                entity_2_id=second,
                entity_2_name=second,
                relationship_description="Shared article activity context",
                confidence=0.5,
                intensity=0.5,
            )
        ]

    @staticmethod
    def to_event_extraction(
        extraction: ConnectionExtraction, article: ArticleIn, primary_firm: str
    ) -> EventExtraction:
        occurred_at = article.article.published_at or datetime.utcnow()
        source_ref = SourceReference(
            url=article.source.url,
            title=article.article.title,
            source_text=extraction.relationship_description
            or article.article.text[:240],
            published_at=article.article.published_at,
            credibility_score=article.source.credibility_score,
            language=article.article.language,
        )
        return EventExtraction(
            event_type=extraction.connection_type,
            event_category="connection",
            title=f"Connection: {primary_firm}",
            description=extraction.relationship_description
            or "Extracted connection event",
            risk_level=max(
                1,
                min(
                    10,
                    int(
                        round(
                            (extraction.confidence or extraction.intensity or 0.5) * 10
                        )
                    ),
                ),
            ),
            occurred_at=occurred_at,
            confidence=extraction.confidence or extraction.intensity or 0.5,
            source_text=extraction.relationship_description
            or article.article.text[:240],
            source_reference=source_ref,
        )

    @staticmethod
    def to_event_out(
        extraction: ConnectionExtraction, article: ArticleIn, primary_firm: str
    ) -> EventOut:
        event = ConnectionExtractor.to_event_extraction(
            extraction, article, primary_firm
        )
        return EventOut(
            event_type=event.event_type,
            risk_level=event.risk_level,
            title=event.title,
            occurred_at=event.occurred_at,
            confidence=event.confidence,
            description=event.description,
            source_text=event.source_text,
        )

    @staticmethod
    def _find_firms(text: str) -> list[str]:
        pattern = re.compile(
            r"\b([A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+)*(?:\s+(?:Corp|Corporation|Ltd|Limited|Inc|Company|Group|Bank)))\b"
        )
        return list(dict.fromkeys(pattern.findall(text)))
