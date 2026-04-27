"""Connection extraction logic for TrustWeb stream."""

from __future__ import annotations

from datetime import datetime

from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import ConnectionExtraction, EventExtraction, PersonExtraction, SourceReference


class ConnectionExtractor:
    def extract_shared_directors(self, article: ArticleIn, people: list[PersonExtraction]) -> list[ConnectionExtraction]:
        if len(people) < 2:
            return []

        source_reference = self._source_ref(article)
        first = people[0]
        second = people[1]
        return [
            ConnectionExtraction(
                connection_type="shared_director",
                entity_1_type="person",
                entity_1_id=first.name,
                entity_1_name=first.name,
                entity_2_type="person",
                entity_2_id=second.name,
                entity_2_name=second.name,
                relationship_description="Potential shared governance inferred from role mentions",
                confidence=0.55,
                source_text=f"{first.source_text} {second.source_text}"[:800],
                source_reference=source_reference,
            )
        ]

    def extract_business_relationships(self, article: ArticleIn, companies: list[str]) -> list[ConnectionExtraction]:
        text = article.article.text.lower()
        keywords = ["partnership", "supplier", "vendor", "client", "joint venture"]
        if len(companies) < 2 or not any(k in text for k in keywords):
            return []

        source_reference = self._source_ref(article)
        return [
            ConnectionExtraction(
                connection_type="business_relationship",
                entity_1_type="company",
                entity_1_id=companies[0],
                entity_1_name=companies[0],
                entity_2_type="company",
                entity_2_id=companies[1],
                entity_2_name=companies[1],
                relationship_description="Business linkage inferred from relationship terms",
                confidence=0.65,
                source_text=article.article.text[:600],
                source_reference=source_reference,
            )
        ]

    def extract_activity_links(self, article: ArticleIn, events: list[EventExtraction]) -> list[ConnectionExtraction]:
        if len(events) < 2:
            return []
        source_reference = self._source_ref(article)
        return [
            ConnectionExtraction(
                connection_type="activity_link",
                entity_1_type="company",
                entity_1_id="company_a",
                entity_1_name="company_a",
                entity_2_type="company",
                entity_2_id="company_b",
                entity_2_name="company_b",
                relationship_description="Multiple suspicious activities in same article window",
                confidence=0.5,
                source_text=" ".join(event.source_text for event in events)[:800],
                source_reference=source_reference,
            )
        ]

    def _source_ref(self, article: ArticleIn) -> SourceReference:
        return SourceReference(
            url=article.source.url,
            title=article.article.title,
            source_text=article.article.text[:500],
            published_at=article.article.published_at or datetime.utcnow(),
            credibility_score=article.source.credibility_score,
            language=article.article.language,
        )
