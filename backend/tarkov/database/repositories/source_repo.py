"""Source repository: Postgres records + standalone Neo4j node creation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import Source
from tarkov.schemas.article import ArticleIn
from tarkov.schemas.parsed_result import EventExtraction, LLMSummary
from tarkov.database.session import get_neo4j_session


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_source(self, source: Source) -> Source:
        self.db.add(source)
        self.db.flush()
        return source

    def create_source_from_article(
        self,
        event_id: str,
        article: ArticleIn,
        llm_summary: LLMSummary | None = None,
    ) -> Source:
        original = Source(
            event_id=event_id,
            url=article.source.url,
            title=article.article.title,
            content=article.article.text,
            source_type="original",
            source_category="article",
            language=article.article.language,
            published_at=article.article.published_at,
            credibility=article.source.credibility_score,
        )
        self.db.add(original)

        try:
            with get_neo4j_session() as g:
                g.create_node("Article", {
                    "source_url": article.source.url,
                    "event_id": event_id,
                })
        except Exception:
            pass

        if llm_summary is not None:
            self.db.add(
                Source(
                    event_id=event_id,
                    url=article.source.url,
                    title=f"LLM Summary: {article.article.title}",
                    content=llm_summary.text,
                    source_type="llm_summary",
                    source_category="summary",
                    language=article.article.language,
                    published_at=article.article.published_at,
                    credibility=llm_summary.confidence,
                )
            )

        self.db.flush()
        return original

    def create_source_with_excerpt(self, event_id: str, extraction: EventExtraction) -> Source:
        evidence = Source(
            event_id=event_id,
            url=extraction.source_reference.url,
            title=extraction.source_reference.title,
            content=extraction.source_text,
            source_type="extraction_evidence",
            source_category="extraction",
            language=extraction.source_reference.language,
            published_at=extraction.source_reference.published_at,
            credibility=extraction.source_reference.credibility_score,
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def get_source(self, source_id: int) -> Source | None:
        return self.db.execute(select(Source).where(Source.id == source_id)).scalar_one_or_none()
