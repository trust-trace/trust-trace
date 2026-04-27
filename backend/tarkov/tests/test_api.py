from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from tarkov.api import create_app
from tarkov.config import Config


def test_article_ingestion_endpoint_processes_payload(tmp_path):
    pytest.importorskip("uvicorn")

    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

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
        api_host="127.0.0.1",
        api_port=8081,
        enable_stage3_dispatch=False,
        event_classifier_url="",
        nsa_url="",
        trustweb_url="",
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
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"processed", "skipped"}
