"""Ingestion job repository for queued article processing."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import IngestionJob
from tarkov.schemas.article import ArticleIn


def build_ingest_key(article: ArticleIn) -> str:
    basis = article.article.canonical_url or f"{article.source.url}|{article.article.title}|{article.article.text}"
    normalized = " ".join(basis.split()).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class IngestionJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, article: ArticleIn, correlation_id: str | None) -> IngestionJob:
        ingest_key = build_ingest_key(article)
        existing = self.get_by_ingest_key(ingest_key)
        if existing is not None:
            return existing

        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            ingest_key=ingest_key,
            request_id=str(uuid.uuid4()),
            correlation_id=correlation_id,
            status="pending",
            payload_json=json.dumps(article.model_dump(mode="json"), ensure_ascii=False),
            source_url=article.source.url,
            title=article.article.title,
            next_retry_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_by_job_id(self, job_id: str) -> IngestionJob | None:
        stmt = select(IngestionJob).where(IngestionJob.job_id == job_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_ingest_key(self, ingest_key: str) -> IngestionJob | None:
        stmt = select(IngestionJob).where(IngestionJob.ingest_key == ingest_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_due_jobs(self, *, limit: int = 10, stale_after_seconds: int = 300) -> list[IngestionJob]:
        stale_cutoff = datetime.utcnow() - timedelta(seconds=stale_after_seconds)
        stmt = select(IngestionJob).where(
            (
                (IngestionJob.status.in_(["pending", "retrying"]))
                & (IngestionJob.next_retry_at.is_(None) | (IngestionJob.next_retry_at <= datetime.utcnow()))
            )
            | (
                (IngestionJob.status == "processing")
                & (IngestionJob.started_at.is_not(None))
                & (IngestionJob.started_at <= stale_cutoff)
            )
        )
        stmt = stmt.order_by(IngestionJob.created_at.asc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def mark_processing(self, job: IngestionJob) -> IngestionJob:
        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.last_error = None
        self.db.flush()
        return job

    def mark_completed(self, job: IngestionJob, *, article_id: str | None, processed_at: datetime | None) -> IngestionJob:
        job.status = "completed"
        job.article_id = article_id
        job.processed_at = processed_at
        job.completed_at = datetime.utcnow()
        job.next_retry_at = None
        self.db.flush()
        return job

    def mark_skipped(self, job: IngestionJob) -> IngestionJob:
        job.status = "skipped"
        job.completed_at = datetime.utcnow()
        job.next_retry_at = None
        self.db.flush()
        return job

    def mark_retry(self, job: IngestionJob, error: str) -> IngestionJob:
        job.attempt_count += 1
        job.last_error = error
        if job.attempt_count >= job.max_attempts:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.next_retry_at = None
        else:
            delay_seconds = min(300, 5 * (2 ** (job.attempt_count - 1)))
            job.status = "retrying"
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self.db.flush()
        return job
