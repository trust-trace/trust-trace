"""Article metadata repository for ingestion tracking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import ArticleMetadata
from tarkov.schemas.article import ArticleIn


class ArticleMetadataRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_ingestion_record(self, article_id: str, correlation_id: str, article: ArticleIn) -> ArticleMetadata:
        obj = ArticleMetadata(
            article_id=article_id,
            correlation_id=correlation_id,
            source_url=article.source.url,
            title=article.article.title,
            published_at=article.article.published_at,
            scraped_at=article.article.scraped_at,
            language=article.article.language,
            region=article.metadata.region,
            companies_found=0,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def mark_processed(self, article_id: str, companies_found: int) -> ArticleMetadata | None:
        obj = self.get_by_article_id(article_id)
        if obj is None:
            return None
        obj.companies_found = max(0, companies_found)
        obj.processed_at = datetime.utcnow()
        self.db.flush()
        return obj

    def get_by_article_id(self, article_id: str) -> ArticleMetadata | None:
        stmt = select(ArticleMetadata).where(ArticleMetadata.article_id == article_id)
        return self.db.execute(stmt).scalar_one_or_none()
