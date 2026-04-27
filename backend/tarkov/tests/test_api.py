"""API ingestion tests."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from tarkov.api import create_app
from tarkov.config import Config
from tarkov.database.models import ArticleMetadata, ConnectionEntity, Event, Firm, IngestionJob, RkrScore
from tarkov.database.session import SessionLocal
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


def wait_for_job(job_id: str, timeout_seconds: float = 5.0) -> IngestionJob:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        db = SessionLocal()
        try:
            job = db.query(IngestionJob).filter_by(job_id=job_id).one_or_none()
            if job is not None and job.status in {"completed", "skipped", "failed"}:
                time.sleep(0.1)
                return job
        finally:
            db.close()
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout_seconds}s")


def sqlite_url(path):
    return f"sqlite+pysqlite:///{path.as_posix()}"


def test_article_ingestion_endpoint_processes_payload(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    config = Config(
        database_url=sqlite_url(tmp_path / "db.sqlite"),
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
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "source": {
            "name": "Reuters",
            "domain": "reuters.com",
            "url": "https://reuters.com/a",
            "credibility_score": 0.9,
            "credibility_label": "high",
        },
        "article": {
            "title": "Acme Corp CEO investigated for fraud",
            "text": "ACME CEO John Smith was named in a fraud investigation and suspicious transaction review.",
            "published_at": "2026-04-27T08:15:00Z",
            "scraped_at": "2026-04-27T08:16:12Z",
            "canonical_url": "https://reuters.com/a",
            "authors": ["Jane Doe"],
            "language": "en",
        },
        "metadata": {
            "section": "markets",
            "region": "us",
            "discovery_method": "rss",
            "http_status": 200,
        },
    }

    response = client.post("/v1/articles", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "started"
    assert wait_for_job(body["job_id"]).status in {"completed", "skipped"}


def test_article_ingestion_accepts_scuttle_word_count(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    config = Config(
        database_url=sqlite_url(tmp_path / "db.sqlite"),
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
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "source": {
            "name": "Reuters",
            "domain": "reuters.com",
            "url": "https://reuters.com/a",
            "credibility_score": 0.9,
            "credibility_label": "high",
        },
        "article": {
            "title": "Acme Corp CEO investigated for fraud",
            "text": "ACME CEO John Smith was named in a fraud investigation and suspicious transaction review.",
            "published_at": "2026-04-27T08:15:00Z",
            "scraped_at": "2026-04-27T08:16:12Z",
            "canonical_url": "https://reuters.com/a",
            "word_count": 845,
            "authors": ["Jane Doe"],
            "language": "en",
        },
        "metadata": {
            "section": "markets",
            "region": "us",
            "discovery_method": "rss",
            "http_status": 200,
        },
    }

    response = client.post("/v1/articles", json=payload)
    assert response.status_code == 202
    wait_for_job(response.json()["job_id"])


def test_article_ingestion_contract_headers_toggle(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    config = Config(
        database_url=sqlite_url(tmp_path / "db.sqlite"),
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
        enable_ingest_contract_headers=True,
        enforce_payload_version_header=True,
        expected_payload_version="1",
    )
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "source": {
            "name": "Reuters",
            "domain": "reuters.com",
            "url": "https://reuters.com/a",
            "credibility_score": 0.9,
            "credibility_label": "high",
        },
        "article": {
            "title": "Acme Corp CEO investigated for fraud",
            "text": "ACME CEO John Smith was named in a fraud investigation and suspicious transaction review.",
            "published_at": "2026-04-27T08:15:00Z",
            "scraped_at": "2026-04-27T08:16:12Z",
            "canonical_url": "https://reuters.com/a",
            "authors": ["Jane Doe"],
            "language": "en",
        },
        "metadata": {
            "section": "markets",
            "region": "us",
            "discovery_method": "rss",
            "http_status": 200,
        },
    }

    bad = client.post("/v1/articles", json=payload)
    assert bad.status_code == 400

    good = client.post(
        "/v1/articles",
        json=payload,
        headers={"X-Payload-Version": "1", "X-Correlation-Id": "cid-test-123"},
    )
    assert good.status_code == 202
    wait_for_job(good.json()["job_id"])


def test_article_ingestion_persists_rkr_and_tarkov(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    config = Config(
        database_url=sqlite_url(tmp_path / "db.sqlite"),
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

    app = create_app(config)
    client = TestClient(app)

    response = client.post("/v1/articles", json=SAMPLE_ARTICLE_1.model_dump(mode="json"))

    assert response.status_code == 202
    assert wait_for_job(response.json()["job_id"]).status == "completed"

    db = SessionLocal()
    try:
        row = db.query(RkrScore).one()
        assert row.request_id
        assert row.passed_threshold is True
        assert row.risk_score > 0
        assert db.query(Firm).count() >= 1
        assert db.query(Event).count() >= 1
        assert db.query(ArticleMetadata).count() >= 1
    finally:
        db.close()


def test_connection_events_are_persisted_without_edges(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}, '
        '{"name": "Beta Bank", "ticker": "BETA", "aliases": ["Beta Bank", "BETA"]}]',
        encoding="utf-8",
    )

    config = Config(
        database_url=sqlite_url(tmp_path / "db.sqlite"),
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
    app = create_app(config)
    client = TestClient(app)

    payload = {
        "source": {
            "name": "Reuters",
            "domain": "reuters.com",
            "url": "https://reuters.com/b",
            "credibility_score": 0.9,
            "credibility_label": "high",
        },
        "article": {
            "title": "Acme Corp and Beta Bank face fraud and money laundering review",
            "text": "Acme Corp and Beta Bank were discussed in a fraud and money laundering review tied to compliance concerns.",
            "published_at": "2026-04-27T08:15:00Z",
            "scraped_at": "2026-04-27T08:16:12Z",
            "canonical_url": "https://reuters.com/b",
            "authors": ["Jane Doe"],
            "language": "en",
        },
        "metadata": {
            "section": "markets",
            "region": "us",
            "discovery_method": "rss",
            "http_status": 200,
        },
    }

    response = client.post("/v1/articles", json=payload)
    assert response.status_code == 202
    assert wait_for_job(response.json()["job_id"]).status == "completed"

    db = SessionLocal()
    try:
        assert db.query(ConnectionEntity).count() >= 1
        assert db.query(Event).filter_by(event_category="connection").count() >= 1
    finally:
        db.close()
