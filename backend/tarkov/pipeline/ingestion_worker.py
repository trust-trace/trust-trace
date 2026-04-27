"""Background ingestion worker that retries failed jobs."""

from __future__ import annotations

import json
import threading
from datetime import datetime

from pydantic import ValidationError

from tarkov.config import Config
from tarkov.database.models import RkrScore
from tarkov.database.repositories.ingestion_job_repo import IngestionJobRepository
from tarkov.database.session import SessionLocal
from tarkov.pipeline.event_handlers import AMLScoringEventHandler
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.pipeline.result_emitter import ResultEmitter
from tarkov.pipeline.stage3_clients import EventClassifierClient, NSAClient
from tarkov.schemas.article import ArticleIn
from tarkov.utils.logger import get_logger
from rkr.pipeline.processor import ArticleProcessor as RkrArticleProcessor


logger = get_logger(__name__)


class IngestionWorker:
    def __init__(self, config: Config, *, poll_interval_seconds: float = 2.0):
        self.config = config
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._rkr_processor = RkrArticleProcessor()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="tarkov-ingestion-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._process_due_jobs()
            except Exception as exc:
                logger.exception("ingestion worker loop failed: %s", exc)
            self._stop_event.wait(self.poll_interval_seconds)

    def _process_due_jobs(self) -> None:
        session = SessionLocal()
        try:
            jobs = IngestionJobRepository(session).get_due_jobs()
            for job in jobs:
                self._process_job(job.job_id)
        finally:
            session.close()

    def _process_job(self, job_id: str) -> None:
        session = SessionLocal()
        try:
            repo = IngestionJobRepository(session)
            job = repo.get_by_job_id(job_id)
            if job is None or job.status in {"completed", "skipped", "failed"}:
                return

            repo.mark_processing(job)
            session.commit()

            raw_payload = json.loads(job.payload_json)
            enriched = self._rkr_processor.process_article(raw_payload)
            logger.info(
                "queued rkr completed risk_score=%s passed=%s categories=%s job_id=%s",
                enriched.rkr.risk_score,
                enriched.rkr.passed_threshold,
                enriched.rkr.categories_hit,
                job.job_id,
            )

            score = RkrScore(
                request_id=job.request_id,
                correlation_id=job.correlation_id,
                source_url=enriched.source["url"],
                title=enriched.article.get("title"),
                language=enriched.article.get("language"),
                threshold=self._rkr_processor.threshold,
                risk_score=enriched.rkr.risk_score,
                passed_threshold=enriched.rkr.passed_threshold,
                categories_hit=json.dumps(enriched.rkr.categories_hit, ensure_ascii=False),
                matched_keywords=json.dumps(enriched.rkr.model_dump().get("matched_keywords", []), ensure_ascii=False),
            )
            session.add(score)
            session.flush()

            if not enriched.rkr.passed_threshold:
                repo.mark_skipped(job)
                session.commit()
                return

            try:
                article = ArticleIn.model_validate(enriched.model_dump())
            except ValidationError as exc:
                repo.mark_retry(job, str(exc))
                session.commit()
                return

            emitter = ResultEmitter()
            if self.config.enable_stage3_dispatch:
                handler = AMLScoringEventHandler(
                    event_classifier_client=EventClassifierClient(self.config.event_classifier_url),
                    nsa_client=NSAClient(self.config.nsa_url),
                )
                emitter.register_async_handler(handler.handle_parsed_event)

            result = ArticleProcessor(session, self.config, result_emitter=emitter).process_article(
                article, correlation_id=job.correlation_id
            )

            repo.mark_completed(
                job,
                article_id=result.article_id if result is not None else None,
                processed_at=result.processed_at if result is not None else datetime.utcnow(),
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            try:
                retry_job = IngestionJobRepository(session).get_by_job_id(job_id)
                if retry_job is not None:
                    IngestionJobRepository(session).mark_retry(retry_job, str(exc))
                    session.commit()
            except Exception:
                session.rollback()
                logger.exception("failed to mark job retry job_id=%s", job_id)
            logger.exception("ingestion job failed job_id=%s: %s", job_id, exc)
        finally:
            session.close()
