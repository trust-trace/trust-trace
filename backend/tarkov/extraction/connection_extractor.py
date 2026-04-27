"""Connection extraction for TrustWeb stream."""

from __future__ import annotations

from datetime import datetime

from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import ConnectionExtraction, EventExtraction, PersonExtraction, SourceReference


class ConnectionExtractor:
    def extract_shared_directors(self, article: ArticleIn, people: list[PersonExtraction]) -> list[ConnectionExtraction]:
        if len(people) < 2:
            return []
        a, b = people[0], people[1]
        return [
            ConnectionExtraction(
                connection_type="shared_director",
                entity_1_type="person",
                entity_1_id=a.name,
                entity_1_name=a.name,
                entity_2_type="person",
                entity_2_id=b.name,
                entity_2_name=b.name,
                relationship_description="Potential shared governance inferred from article",
                confidence=0.55,
                source_text=f"{a.source_text} {b.source_text}"[:800],
                source_reference=self._source_ref(article),
                intensity=0.5,  # Placeholder intensity value
            )
        ]

    def extract_business_relationships(self, article: ArticleIn, companies: list[str]) -> list[ConnectionExtraction]:
        if len(companies) < 2:
            return []
        text = article.article.text.lower()
        if not any(k in text for k in ["partnership", "supplier", "vendor", "client", "joint venture"]):
            return []
        return [
            ConnectionExtraction(
                connection_type="business_relationship",
                entity_1_type="company",
                entity_1_id=companies[0],
                entity_1_name=companies[0],
                entity_2_type="company",
                entity_2_id=companies[1],
                entity_2_name=companies[1],
                relationship_description="Business relationship inferred from article language",
                confidence=0.65,
                source_text=article.article.text[:600],
                source_reference=self._source_ref(article),
                intensity=0.7,  # Placeholder intensity value
            )
        ]

    def extract_activity_links(self, article: ArticleIn, events: list[EventExtraction]) -> list[ConnectionExtraction]:
        if len(events) < 2:
            return []
        return [
            ConnectionExtraction(
                connection_type="activity_link",
                entity_1_type="company",
                entity_1_id="company_a",
                entity_1_name="company_a",
                entity_2_type="company",
                entity_2_id="company_b",
                entity_2_name="company_b",
                relationship_description="Shared suspicious activity in one article context",
                confidence=0.5,
                source_text=" ".join(e.source_text for e in events)[:800],
                source_reference=self._source_ref(article),
                intensity=0.6,  # Placeholder intensity value
            )
        ]

    @staticmethod
    def _source_ref(article: ArticleIn) -> SourceReference:
        return SourceReference(
            url=article.source.url,
            title=article.article.title,
            source_text=article.article.text[:500],
            published_at=article.article.published_at or datetime.utcnow(),
            credibility_score=article.source.credibility_score,
            language=article.article.language,
        )
