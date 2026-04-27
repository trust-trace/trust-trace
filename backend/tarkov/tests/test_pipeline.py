"""Pipeline tests."""

from __future__ import annotations

from tarkov.config import Config
from tarkov.database.models import ArticleMetadata
from tarkov.database.session import Base, init_engine
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


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
