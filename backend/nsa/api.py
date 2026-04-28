from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from nsa.database.repository import NsaRepository
from nsa.database.session import SessionLocal, close_engine, create_all, get_database_url, get_engine, init_engine
from nsa.fetchers.news import NewsFetcher
from nsa.fetchers.registry import RegistryFetcher
from nsa.fetchers.sanctions import SanctionsFetcher
from nsa.scoring.service import NSAService
from nsa.schemas.api import ScoreCompanyRequest, ScoreCompanyResponse
from reasoning.storage import ReasoningTraceRepository


def _prepare_reasoning_schema(engine) -> None:
    import reasoning.models  # noqa: F401 — registers ReasoningTraceModel on ReasoningBase
    from reasoning.session import Base as ReasoningBase
    ReasoningBase.metadata.create_all(bind=engine)


class StubNSAService:
    def score_company(self, firm_id: int, correlation_id: str, include_reasoning: bool = True) -> ScoreCompanyResponse:
        return ScoreCompanyResponse(
            status="ok",
            firm_id=firm_id,
            company_risk_score=0.62,
            people_scored=3,
            evidence_count=11,
        )


def build_service(database_url: str) -> NSAService:
    current_database_url = get_database_url()
    try:
        get_engine()
    except RuntimeError:
        init_engine(database_url)
    else:
        if current_database_url != database_url:
            init_engine(database_url)
    session = SessionLocal()
    repository = NsaRepository(session)
    fetchers = [RegistryFetcher(), SanctionsFetcher(), NewsFetcher()]
    return NSAService(repository=repository, fetchers=fetchers)


def create_app(service: StubNSAService | None = None, database_url: str = "sqlite+pysqlite:///:memory:") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if service is None:
            init_engine(database_url)
            create_all()
            _prepare_reasoning_schema(get_engine())
        try:
            yield
        finally:
            close_engine()

    app = FastAPI(title="NSA API", version="0.1.0", lifespan=lifespan)

    def _close_service(scoring_service: NSAService) -> None:
        repository = getattr(scoring_service, "repository", None)
        session = getattr(repository, "session", None)
        if session is not None:
            session.close()

    @app.post("/score/company", response_model=ScoreCompanyResponse)
    def score_company(payload: ScoreCompanyRequest) -> ScoreCompanyResponse:
        if service is not None:
            return service.score_company(
                payload.firm_id, payload.correlation_id, include_reasoning=payload.include_reasoning
            )

        scoring_service = build_service(database_url)
        try:
            return scoring_service.score_company(
                payload.firm_id,
                payload.correlation_id,
                db_session=scoring_service.repository.session,
                include_reasoning=payload.include_reasoning,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            _close_service(scoring_service)

    @app.get("/score/traces/correlation/{correlation_id}")
    def get_traces_by_correlation(correlation_id: str) -> list[dict]:
        session = SessionLocal()
        try:
            repo = ReasoningTraceRepository(session)
            traces = repo.get_by_correlation_id(correlation_id)
            return [t.model_dump(mode="json") for t in traces]
        finally:
            session.close()

    @app.get("/score/traces/{entity_id}")
    def get_traces_by_entity(entity_id: str, classifier: str | None = None) -> list[dict]:
        session = SessionLocal()
        try:
            repo = ReasoningTraceRepository(session)
            if classifier:
                traces = repo.get_by_classifier_and_entity_id(classifier, entity_id)
            else:
                traces = repo.get_by_entity_id(entity_id)
            return [t.model_dump(mode="json") for t in traces]
        finally:
            session.close()

    return app
