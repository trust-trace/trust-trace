"""Pipeline tests."""

from __future__ import annotations

from datetime import datetime

from tarkov.config import Config
from tarkov.database.models import ArticleMetadata
from tarkov.database.session import Base, init_engine
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.schemas.parsed_result import LLMSummary, ParsedResult, ParsingEvent
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


class NSAClientStub:
    def __init__(self):
        self.calls = []

    async def score_company(self, firm_id, correlation_id):
        self.calls.append((firm_id, correlation_id))
        return {"status": "ok", "firm_id": firm_id}


class EventClassifierStub:
    def __init__(self):
        self.calls = []

    async def score_events(self, company_matches, events, correlation_id):
        self.calls.append((company_matches, events, correlation_id))
        return {"status": "ok"}


def test_process_article_full_flow(tmp_path):
    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    engine = init_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    from tarkov.database.session import SessionLocal

    db = SessionLocal()
    config = Config(
        database_url="sqlite+pysqlite:///:memory:",
        log_level="INFO",
        llm_provider="openai",
        llm_api_key="",
        llm_model="gpt-4o-mini",
        article_input_source="jsonl",
        article_input_path="",
        company_reference_path=str(companies),
        keywords_file_path="",
        dead_letter_path=str(tmp_path / "dead_letters.jsonl"),
        api_host="127.0.0.1",
        api_port=8081,
        enable_stage3_dispatch=False,
        event_classifier_url="",
        nsa_url="",
        trustweb_url="",
        enable_ingest_contract_headers=False,
        enforce_payload_version_header=False,
        expected_payload_version="1",
    )
    processor = ArticleProcessor(db, config)
    result = processor.process_article(SAMPLE_ARTICLE_1)
    assert result is not None
    assert len(result.company_matches) >= 1
    metadata = db.query(ArticleMetadata).filter_by(article_id=result.article_id).one_or_none()
    assert metadata is not None
    assert metadata.correlation_id
    assert metadata.source_url == SAMPLE_ARTICLE_1.source.url
    assert metadata.title == SAMPLE_ARTICLE_1.article.title
    assert metadata.processed_at is not None
    assert metadata.companies_found >= 1
    assert metadata.discovery_method == SAMPLE_ARTICLE_1.metadata.discovery_method
    assert metadata.http_status == SAMPLE_ARTICLE_1.metadata.http_status
    assert metadata.canonical_url == SAMPLE_ARTICLE_1.article.canonical_url
    assert metadata.word_count is None


def test_stage3_event_handler_dispatches_nsa_with_firm_ids() -> None:
    from tarkov.pipeline.event_handlers import AMLScoringEventHandler

    event_classifier = EventClassifierStub()
    nsa = NSAClientStub()
    handler = AMLScoringEventHandler(event_classifier, nsa)
    parsed_result = ParsedResult(
        article_id="article-1",
        processed_at=datetime.utcnow(),
        llm_summary=LLMSummary(text="summary", confidence=1.0),
        firm_ids=[123],
    )
    event = ParsingEvent(
        timestamp=parsed_result.processed_at,
        parsed_result=parsed_result,
        firm_ids=list(parsed_result.firm_ids),
        correlation_id="cid-1",
    )

    import asyncio

    asyncio.run(handler.handle_parsed_event(event))

    assert event.firm_ids == [123]
    assert nsa.calls == [(123, "cid-1")]
    assert event_classifier.calls == []


def test_stage3_event_handler_dispatches_all_persisted_firm_ids() -> None:
    from tarkov.pipeline.event_handlers import AMLScoringEventHandler

    event_classifier = EventClassifierStub()
    nsa = NSAClientStub()
    handler = AMLScoringEventHandler(event_classifier, nsa)
    parsed_result = ParsedResult(
        article_id="article-2",
        processed_at=datetime.utcnow(),
        llm_summary=LLMSummary(text="summary", confidence=1.0),
        firm_ids=[101, 202, 303],
    )
    event = ParsingEvent(
        timestamp=parsed_result.processed_at,
        parsed_result=parsed_result,
        firm_ids=list(parsed_result.firm_ids),
        correlation_id="cid-2",
    )

    import asyncio

    asyncio.run(handler.handle_parsed_event(event))

    assert event.firm_ids == [101, 202, 303]
    assert nsa.calls == [(101, "cid-2"), (202, "cid-2"), (303, "cid-2")]
    assert event_classifier.calls == []


def test_stage3_event_handler_skips_nsa_when_no_firm_ids_present() -> None:
    from tarkov.pipeline.event_handlers import AMLScoringEventHandler

    event_classifier = EventClassifierStub()
    nsa = NSAClientStub()
    handler = AMLScoringEventHandler(event_classifier, nsa)
    parsed_result = ParsedResult(
        article_id="article-5",
        processed_at=datetime.utcnow(),
        llm_summary=LLMSummary(text="summary", confidence=1.0),
        firm_ids=[],
    )
    event = ParsingEvent(
        timestamp=parsed_result.processed_at,
        parsed_result=parsed_result,
        correlation_id="cid-5",
    )

    import asyncio

    asyncio.run(handler.handle_parsed_event(event))

    assert nsa.calls == []
    assert event_classifier.calls == []


def test_parsing_event_fills_firm_ids_from_parsed_result() -> None:
    parsed_result = ParsedResult(
        article_id="article-3",
        processed_at=datetime.utcnow(),
        llm_summary=LLMSummary(text="summary", confidence=1.0),
        firm_ids=[7, 8],
    )

    event = ParsingEvent(
        timestamp=parsed_result.processed_at,
        parsed_result=parsed_result,
        correlation_id="cid-3",
    )

    assert event.firm_ids == [7, 8]


def test_parsing_event_rejects_mismatched_firm_ids() -> None:
    parsed_result = ParsedResult(
        article_id="article-4",
        processed_at=datetime.utcnow(),
        llm_summary=LLMSummary(text="summary", confidence=1.0),
        firm_ids=[11],
    )

    import pytest

    with pytest.raises(ValueError, match="firm_ids must match parsed_result.firm_ids"):
        ParsingEvent(
            timestamp=parsed_result.processed_at,
            parsed_result=parsed_result,
            firm_ids=[12],
            correlation_id="cid-4",
        )
