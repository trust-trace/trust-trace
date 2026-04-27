"""HTTP API for receiving Stage 1 payloads from Scuttle Crab."""

from __future__ import annotations

from sqlalchemy import text

from tarkov.config import Config
from tarkov.database.session import SessionLocal, create_all, init_engine
from tarkov.pipeline.event_handlers import AMLScoringEventHandler
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.pipeline.result_emitter import ResultEmitter
from tarkov.pipeline.stage3_clients import EventClassifierClient, NSAClient, TrustWebClient
from tarkov.schemas.article import ArticleIn
from tarkov.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


def _check_db_connection() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


def create_app(config: Config | None = None):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is required to run Tarkov API. Install dependencies from backend/requirements.txt"
        ) from exc

    cfg = config or Config.from_env()
    setup_logging(cfg.log_level)
    init_engine(cfg.database_url)
    create_all()

    app = FastAPI(
        title="Tarkov API",
        version="0.1.0",
        description="Receives normalized article payloads from Scuttle Crab and runs Stage 2 extraction.",
    )

    @app.get("/health")
    def health() -> dict:
        try:
            _check_db_connection()
            return {"status": "ok", "service": "tarkov", "db": "ok"}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"DB health check failed: {exc}") from exc

    @app.post("/v1/articles")
    def receive_article(article: ArticleIn):
        session = SessionLocal()
        try:
            emitter = ResultEmitter()
            if cfg.enable_stage3_dispatch:
                handler = AMLScoringEventHandler(
                    event_classifier_client=EventClassifierClient(cfg.event_classifier_url),
                    nsa_client=NSAClient(cfg.nsa_url),
                    trustweb_client=TrustWebClient(cfg.trustweb_url),
                )
                emitter.register_async_handler(handler.handle_parsed_event)

            processor = ArticleProcessor(session, cfg, result_emitter=emitter)
            result = processor.process_article(article)
            if result is None:
                return {
                    "status": "skipped",
                    "reason": "no_company_matches",
                    "title": article.article.title,
                }

            return {
                "status": "processed",
                "article_id": result.article_id,
                "events": len(result.events),
                "people": len(result.people),
                "connections": len(result.connections),
                "company_matches": result.company_matches,
                "total_risk_score": result.total_risk_score,
            }
        except Exception as exc:
            logger.exception("Article processing failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            session.close()

    return app


app = create_app()
