from __future__ import annotations

from tarkov.config import Config
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
        llm_provider="openai",
        llm_api_key="",
        llm_model="gpt-4o-mini",
        log_level="INFO",
        keywords_file_path="",
        article_input_source="jsonl",
        article_input_path="",
        company_reference_path=str(companies),
        dead_letter_path=str(tmp_path / "dead_letters.jsonl"),
    )
    processor = ArticleProcessor(db, config)
    result = processor.process_article(SAMPLE_ARTICLE_1)
    assert result is not None
    assert len(result.company_matches) >= 1
