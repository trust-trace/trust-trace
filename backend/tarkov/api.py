"""FastAPI application for Stage 1 -> Stage 2 ingestion."""

from __future__ import annotations

import asyncio
import json
import os
import uuid

from sqlalchemy import text

try:
    from fastapi import Request as FastAPIRequest
except ImportError:  # pragma: no cover - guarded again in create_app
    FastAPIRequest = object

from tarkov.config import Config
from tarkov.database.repositories.ingestion_job_repo import IngestionJobRepository
from tarkov.database.session import SessionLocal, create_all, get_engine, init_engine
from tarkov.frontend_graph_api import FrontendGraphService
from tarkov.pipeline.ingestion_worker import IngestionWorker
from tarkov.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


def _check_db_connection() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


def _prepare_eem_schema() -> None:
    from eem.database.session import Base as EemBase

    import eem.database.models  # noqa: F401  # populate metadata

    EemBase.metadata.create_all(bind=get_engine())


def _prepare_pipeline_schema() -> None:
    import pipeline.models  # noqa: F401  # populate metadata on Tarkov's Base

    from tarkov.database.session import Base
    Base.metadata.create_all(bind=get_engine())


def _prepare_reasoning_schema() -> None:
    import reasoning.models  # noqa: F401  # registers ReasoningTraceModel on ReasoningBase
    from reasoning.session import Base as ReasoningBase
    ReasoningBase.metadata.create_all(bind=get_engine())


def create_app(config: Config | None = None):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError("FastAPI is required to run Tarkov API") from exc

    cfg = config or Config.from_env()
    setup_logging(cfg.log_level)
    init_engine(cfg.database_url)
    create_all()
    _prepare_eem_schema()
    _prepare_pipeline_schema()
    _prepare_reasoning_schema()

    app = FastAPI(title="Tarkov API", version="0.1.0")
    worker = IngestionWorker(cfg)
    frontend_graph_service = FrontendGraphService(cfg)
    worker.prepare_eem()
    worker.start()

    @app.on_event("startup")
    def _startup_ingestion_worker() -> None:
        worker.start()

    @app.on_event("shutdown")
    def _shutdown_ingestion_worker() -> None:
        worker.stop()

    @app.get("/health")
    def health() -> dict:
        try:
            _check_db_connection()
            return {"status": "ok", "service": "tarkov", "db": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"DB health check failed: {exc}"
            ) from exc

    @app.get("/api/companies")
    def list_frontend_companies() -> list[dict]:
        session = SessionLocal()
        try:
            return frontend_graph_service.list_companies(session)
        except Exception as exc:
            logger.exception("Failed to load frontend companies: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to load companies"
            ) from exc
        finally:
            session.close()

    @app.get("/api/relations")
    def list_frontend_relations() -> list[dict]:
        session = SessionLocal()
        try:
            return frontend_graph_service.list_relations(session)
        except Exception as exc:
            logger.exception("Failed to load frontend relations: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to load relations"
            ) from exc
        finally:
            session.close()

    @app.get("/api/companies/{company_id}/articles")
    def list_frontend_company_articles(company_id: str) -> list[dict]:
        session = SessionLocal()
        try:
            return frontend_graph_service.list_articles(session, company_id)
        except Exception as exc:
            logger.exception(
                "Failed to load frontend articles for %s: %s", company_id, exc
            )
            raise HTTPException(
                status_code=500, detail="Failed to load company articles"
            ) from exc
        finally:
            session.close()

    @app.get("/api/graph/{company_id}")
    def get_frontend_graph(company_id: str, max_depth: int = 2) -> dict:
        session = SessionLocal()
        try:
            return frontend_graph_service.get_graph(
                session, company_id, max_depth=max_depth
            )
        except Exception as exc:
            logger.exception(
                "Failed to load frontend graph for %s: %s", company_id, exc
            )
            raise HTTPException(status_code=500, detail="Failed to load graph") from exc
        finally:
            session.close()

    @app.post("/v1/articles", status_code=202)
    async def receive_article(request: FastAPIRequest, include_reasoning: bool = False):
        try:
            raw_payload = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON payload: {exc}"
            ) from exc

        if not isinstance(raw_payload, dict):
            raise HTTPException(
                status_code=400, detail="Expected a JSON object payload"
            )

        correlation_id = None
        if cfg.enable_ingest_contract_headers:
            correlation_id = request.headers.get(
                "X-Correlation-Id"
            ) or request.headers.get("x-correlation-id")
            payload_version = request.headers.get(
                "X-Payload-Version"
            ) or request.headers.get("x-payload-version")
            if (
                cfg.enforce_payload_version_header
                and payload_version != cfg.expected_payload_version
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unsupported payload version. "
                        f"Expected {cfg.expected_payload_version}, got {payload_version!r}"
                    ),
                )

        session = SessionLocal()
        try:
            try:
                from tarkov.schemas.article import ArticleIn

                article = ArticleIn.model_validate(raw_payload)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            job = IngestionJobRepository(session).enqueue(
                article, correlation_id or str(uuid.uuid4())
            )
            session.commit()
            return {
                "status": "started",
                "job_id": job.job_id,
                "ingest_key": job.ingest_key,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to queue article: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            session.close()

    @app.get("/v1/articles/{job_id}")
    def article_job_status(job_id: str) -> dict:
        session = SessionLocal()
        try:
            job = IngestionJobRepository(session).get_by_job_id(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            return {
                "job_id": job.job_id,
                "status": job.status,
                "attempt_count": job.attempt_count,
                "last_error": job.last_error,
                "article_id": job.article_id,
                "source_url": job.source_url,
                "title": job.title,
            }
        finally:
            session.close()

    # ── Pipeline endpoints ────────────────────────────────────────────

    @app.post("/v1/pipeline/run", status_code=202)
    async def pipeline_run(request: FastAPIRequest):
        """Kick off the full E2E AML scoring pipeline.

        Request body: ``{"query": "<keyword or company>", "article_limit": 30}``
        Returns 202 with ``run_id`` immediately; pipeline executes in background.
        """
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

        query = body.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="'query' is required")

        article_limit = int(body.get("article_limit", 30))

        from pipeline.orchestrator import PipelineOrchestrator
        from pipeline.scraper_adapter import ScuttleCrabAdapter

        scuttle_url = os.environ.get("SCUTTLE_CRAB_URL", "").strip()
        scraper = ScuttleCrabAdapter(scuttle_url) if scuttle_url else None
        orchestrator = PipelineOrchestrator(cfg, scraper=scraper)
        run_id = str(uuid.uuid4())

        # Create the pipeline_run row synchronously so the ID is available
        from pipeline.models import PipelineRun as PipelineRunModel
        session = SessionLocal()
        try:
            run = PipelineRunModel(
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

        async def _background():
            try:
                await orchestrator._execute(run_id, query, article_limit)
                orchestrator._complete(run_id, {})
            except Exception as exc:
                logger.exception("Pipeline %s failed", run_id)
                orchestrator._fail(run_id, str(exc))

        asyncio.create_task(_background())

        return {"status": "accepted", "run_id": run_id}

    @app.get("/api/v1/traces/correlation/{correlation_id}")
    def get_traces_by_correlation(correlation_id: str) -> list[dict]:
        from reasoning.storage import ReasoningTraceRepository
        session = SessionLocal()
        try:
            repo = ReasoningTraceRepository(session)
            traces = repo.get_by_correlation_id(correlation_id)
            return [t.model_dump(mode="json") for t in traces]
        finally:
            session.close()

    @app.get("/api/v1/traces/{classifier}/{entity_id}")
    def get_traces(classifier: str, entity_id: str) -> list[dict]:
        from reasoning.storage import ReasoningTraceRepository
        session = SessionLocal()
        try:
            repo = ReasoningTraceRepository(session)
            traces = repo.get_by_classifier_and_entity_id(classifier, entity_id)
            return [t.model_dump(mode="json") for t in traces]
        finally:
            session.close()

    @app.get("/v1/pipeline/{run_id}")
    def pipeline_status(run_id: str) -> dict:
        """Poll the current state of a pipeline run."""
        from pipeline.models import PipelineRun as PipelineRunModel

        session = SessionLocal()
        try:
            run = session.get(PipelineRunModel, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Pipeline run not found")
            return {
                "run_id": run.id,
                "query": run.query,
                "status": run.status,
                "phase": run.phase,
                "article_target": run.article_target,
                "articles_scraped": run.articles_scraped,
                "articles_processed": run.articles_processed,
                "firm_ids": json.loads(run.firm_ids) if run.firm_ids else [],
                "final_scores": json.loads(run.final_scores) if run.final_scores else {},
                "error": run.error,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
        finally:
            session.close()

    return app
