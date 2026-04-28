"""E2E pipeline orchestrator.

Manages the full lifecycle::

    CREATED → SCRAPING → INGESTING → GATHERING → SCORING → MERGING → COMPLETE

Each phase transition updates the ``pipeline_run`` row.  If any phase
fails the run is moved to a ``FAILED_<phase>`` status.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from eem import EEMTimelineEntry, enrich_firm as eem_enrich_firm
from pipeline.firm_enricher import FirmEnricher
from pipeline.models import FinalScoreTimeline, PipelineRun
from pipeline.score_merger import ScoreMerger
from pipeline.scraper_adapter import MockScraperAdapter, ScraperAdapter, ScrapeResult
from tarkov.config import Config as TarkovConfig
from tarkov.database.models import Firm, IngestionJob
from tarkov.database.repositories.ingestion_job_repo import IngestionJobRepository
from tarkov.database.session import SessionLocal
from tarkov.schemas.article import ArticleIn
from timeline.buckets import TimelineBucket, compute_timeline_buckets
from trust_web import score_firm as trustweb_score_firm
from trust_web.schemas import TrustWebTimelineResult

logger = logging.getLogger(__name__)

PHASES = [
    "created",
    "scraping",
    "ingesting",
    "gathering",
    "scoring",
    "merging",
    "complete",
]


class PipelineOrchestrator:
    """Async orchestrator that drives the full E2E pipeline for a query."""

    def __init__(
        self,
        tarkov_config: TarkovConfig,
        *,
        scraper: ScraperAdapter | None = None,
    ) -> None:
        self._config = tarkov_config
        self._scraper = scraper or MockScraperAdapter()
        self._merger = ScoreMerger()

    async def run(self, query: str, article_limit: int = 30) -> str:
        """Execute the full pipeline.  Returns the ``run_id``."""
        run_id = str(uuid.uuid4())

        session = SessionLocal()
        try:
            run = PipelineRun(
                id=run_id,
                query=query,
                status="running",
                phase="created",
                article_target=article_limit,
            )
            session.add(run)
            session.commit()
        finally:
            session.close()

        try:
            await self._execute(run_id, query, article_limit)
        except Exception as exc:
            logger.exception("Pipeline %s failed", run_id)
            self._fail(run_id, str(exc))

        return run_id

    # ── Phase implementations ────────────────────────────────────────────

    async def _execute(self, run_id: str, query: str, article_limit: int) -> None:
        # Phase 2: Scraping
        self._update_phase(run_id, "scraping")
        result = await self._scraper.scrape(query, article_limit)

        if result.delivered_directly:
            # Scuttle Crab already pushed articles to Tarkov — skip
            # manual enqueue and go straight to waiting for ingestion.
            self._update_field(run_id, "articles_scraped", result.delivered_count)
            self._update_phase(run_id, "ingesting")
            job_ids: list[str] = []
        else:
            self._update_field(run_id, "articles_scraped", len(result.articles))
            # Phase 3+4: Ingesting (RKR + Tarkov, via ingestion jobs)
            self._update_phase(run_id, "ingesting")
            job_ids = self._enqueue_articles(run_id, result.articles)

        if result.delivered_directly:
            # Articles were pushed to Tarkov by Scuttle Crab.  Give Tarkov
            # time to ingest, then collect all firms that have events.
            if result.delivered_count > 0:
                await asyncio.sleep(min(result.delivered_count * 2.0, 30.0))
            firm_ids = self._collect_all_firm_ids()
        else:
            await self._wait_for_ingestion(run_id, job_ids)
            firm_ids = self._collect_firm_ids(job_ids)
        self._update_field(run_id, "firm_ids", json.dumps(firm_ids))

        if not firm_ids:
            self._update_phase(run_id, "complete")
            self._complete(run_id, {})
            return

        # Phase 5: Gathering (post-ingestion enrichment)
        self._update_phase(run_id, "gathering")
        self._enrich_firms(firm_ids)

        # Phase 6+7: Scoring (EEM + TrustWeb + NSA in parallel per firm)
        self._update_phase(run_id, "scoring")
        all_scores: dict[int, dict] = {}
        for firm_id in firm_ids:
            scores = await self._score_firm(firm_id)
            all_scores[firm_id] = scores

        # Phase 8: Merging
        self._update_phase(run_id, "merging")
        for firm_id, scores in all_scores.items():
            self._merge_and_persist(run_id, firm_id, scores)

        # Done
        summary = {
            str(fid): {
                "latest_final_score": scores.get("merged_latest"),
            }
            for fid, scores in all_scores.items()
        }
        self._complete(run_id, summary)

    # ── Phase 2: Scraping ────────────────────────────────────────────────

    def _enqueue_articles(self, run_id: str, articles: list[dict]) -> list[str]:
        """Feed scraped article payloads into the ingestion queue."""
        session = SessionLocal()
        job_ids: list[str] = []
        try:
            repo = IngestionJobRepository(session)
            for raw in articles:
                try:
                    article = ArticleIn.model_validate(raw)
                except Exception:
                    logger.warning("Skipping malformed article payload")
                    continue

                # Tag with run_id via correlation_id
                job = repo.enqueue(article, run_id)
                job_ids.append(job.job_id)
            session.commit()
        finally:
            session.close()

        logger.info("Enqueued %d articles for run %s", len(job_ids), run_id)
        return job_ids

    async def _wait_for_ingestion(
        self,
        run_id: str,
        job_ids: list[str],
        *,
        timeout_seconds: int = 600,
        poll_interval: float = 2.0,
    ) -> None:
        """Poll until all ingestion jobs reach a terminal state."""
        terminal = {"completed", "skipped", "failed"}
        start = datetime.utcnow()

        while True:
            session = SessionLocal()
            try:
                repo = IngestionJobRepository(session)
                done = 0
                for jid in job_ids:
                    job = repo.get_by_job_id(jid)
                    if job and job.status in terminal:
                        done += 1
                self._update_field(run_id, "articles_processed", done)
            finally:
                session.close()

            if done >= len(job_ids):
                break

            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning("Ingestion timed out for run %s (%d/%d done)", run_id, done, len(job_ids))
                break

            await asyncio.sleep(poll_interval)

    def _collect_firm_ids(self, job_ids: list[str]) -> list[int]:
        """Extract unique firm IDs from completed ingestion jobs."""
        session = SessionLocal()
        firm_ids: set[int] = set()
        try:
            repo = IngestionJobRepository(session)
            for jid in job_ids:
                job = repo.get_by_job_id(jid)
                if job and job.status == "completed" and job.article_id:
                    from sqlalchemy import text
                    rows = session.execute(
                        text("SELECT DISTINCT firm_id FROM event WHERE firm_id IS NOT NULL"),
                    ).fetchall()
                    for r in rows:
                        firm_ids.add(r.firm_id)
        finally:
            session.close()
        return sorted(firm_ids)

    def _collect_all_firm_ids(self) -> list[int]:
        """Return all firm IDs that have at least one event row."""
        session = SessionLocal()
        try:
            from sqlalchemy import text
            rows = session.execute(
                text("SELECT DISTINCT firm_id FROM event WHERE firm_id IS NOT NULL"),
            ).fetchall()
            return sorted({r.firm_id for r in rows})
        finally:
            session.close()

    # ── Phase 5: Gathering ───────────────────────────────────────────────

    def _enrich_firms(self, firm_ids: list[int]) -> None:
        session = SessionLocal()
        try:
            enricher = FirmEnricher(session)
            enricher.enrich_all(firm_ids)
            session.commit()
        finally:
            session.close()

    # ── Phase 6+7: Scoring ───────────────────────────────────────────────

    async def _score_firm(self, firm_id: int) -> dict:
        """Run EEM, TrustWeb, and NSA in parallel for one firm."""

        async def _run_eem() -> list[EEMTimelineEntry]:
            return await asyncio.to_thread(eem_enrich_firm, firm_id)

        async def _run_trustweb() -> TrustWebTimelineResult:
            return await trustweb_score_firm(firm_id, force_rescore=True)

        async def _run_nsa():
            from nsa.api import StubNSAService
            svc = StubNSAService()
            return await asyncio.to_thread(svc.score_company, firm_id, "pipeline")

        results: dict = {
            "eem_timeline": None,
            "trustweb_timeline": None,
            "nsa_score": None,
            "merged_latest": None,
        }

        tasks = {
            "eem": asyncio.create_task(_run_eem()),
            "trustweb": asyncio.create_task(_run_trustweb()),
            "nsa": asyncio.create_task(_run_nsa()),
        }

        done, _ = await asyncio.wait(tasks.values(), return_when=asyncio.ALL_COMPLETED)

        for name, task in tasks.items():
            if task.exception() is not None:
                logger.error("Scoring module %s failed for firm %d: %s", name, firm_id, task.exception())
                continue
            result = task.result()
            if name == "eem":
                results["eem_timeline"] = result
            elif name == "trustweb":
                results["trustweb_timeline"] = result
            elif name == "nsa":
                results["nsa_score"] = result.company_risk_score if result else None

        return results

    # ── Phase 8: Merging ─────────────────────────────────────────────────

    def _merge_and_persist(self, run_id: str, firm_id: int, scores: dict) -> None:
        session = SessionLocal()
        try:
            firm = session.get(Firm, firm_id)
            if firm is None:
                return

            founding = firm.founded_at or firm.created_at or datetime.utcnow()
            buckets = compute_timeline_buckets(founding)

            eem_timeline: list[EEMTimelineEntry] | None = scores.get("eem_timeline")
            tw_result: TrustWebTimelineResult | None = scores.get("trustweb_timeline")
            nsa_score: float | None = scores.get("nsa_score")

            eem_scores: list[float | None] = []
            if eem_timeline:
                eem_scores = [float(e.score) for e in eem_timeline]
            else:
                eem_scores = [None] * len(buckets)

            tw_scores: list[float | None] = []
            if tw_result:
                tw_scores = [e.score for e in tw_result.entries]
            else:
                tw_scores = [None] * len(buckets)

            merged = self._merger.merge(buckets, eem_scores, tw_scores, nsa_score)
            rows = self._merger.to_db_rows(firm_id, run_id, merged)
            for row in rows:
                session.add(row)
            session.commit()

            if merged:
                scores["merged_latest"] = merged[-1].final_score

            logger.info(
                "Merged scores for firm %d run %s: latest=%.4f",
                firm_id, run_id, merged[-1].final_score if merged else 0.0,
            )
        except Exception:
            session.rollback()
            logger.exception("Failed to merge scores for firm %d", firm_id)
        finally:
            session.close()

    # ── State management ─────────────────────────────────────────────────

    def _update_phase(self, run_id: str, phase: str) -> None:
        session = SessionLocal()
        try:
            run = session.get(PipelineRun, run_id)
            if run:
                run.phase = phase
                run.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _update_field(self, run_id: str, field: str, value) -> None:
        session = SessionLocal()
        try:
            run = session.get(PipelineRun, run_id)
            if run:
                setattr(run, field, value)
                run.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _fail(self, run_id: str, error: str) -> None:
        session = SessionLocal()
        try:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = f"failed_{run.phase}"
                run.error = error[:2000]
                run.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def _complete(self, run_id: str, summary: dict) -> None:
        session = SessionLocal()
        try:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = "complete"
                run.phase = "complete"
                run.final_scores = json.dumps(summary)
                run.completed_at = datetime.utcnow()
                run.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()
