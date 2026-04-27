"""Hybrid extraction tests."""

from __future__ import annotations

from tarkov.config import Config
from tarkov.database.session import Base, SessionLocal, init_engine
from tarkov.extraction.company_matcher import CompanyMatcher
from tarkov.extraction.connection_extractor import ConnectionExtractor
from tarkov.extraction.person_extractor import PersonExtractor
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


class FakeLLMClient:
    has_api_key = True

    def match_companies(self, article_text: str, candidates: list[dict]):
        return [
            {
                "company_name": "Acme Corp",
                "ticker": "ACME",
                "matched_text": "ACME",
                "confidence": 0.97,
            }
        ]

    def extract_people_hybrid(self, article_text: str, event_context: str, candidates: list[dict]):
        return [
            {
                "name": "John Smith",
                "role": "ceo",
                "description": "Named as CEO in the article",
                "confidence": 0.92,
                "source_text": "CEO John Smith of Acme Corp",
            }
        ]

    def extract_connections_hybrid(self, article_text: str, companies: list[str], people: list[str], events: list[str]):
        return [
            {
                "connection_type": "business_relationship",
                "entity_1_type": "company",
                "entity_1_id": "Acme Corp",
                "entity_1_name": "Acme Corp",
                "entity_2_type": "company",
                "entity_2_id": "Beta Bank",
                "entity_2_name": "Beta Bank",
                "relationship_description": "Multihop relationship inferred from the article context",
                "confidence": 0.81,
                "intensity": 0.74,
            }
        ]


def _company_config(company_path: str) -> Config:
    return Config(
        database_url="sqlite+pysqlite:///:memory:",
        log_level="INFO",
        llm_provider="openai",
        llm_api_key="test-key",
        llm_model="gpt-4o-mini",
        article_input_source="jsonl",
        article_input_path="",
        company_reference_path=company_path,
        keywords_file_path="",
        dead_letter_path="",
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


def test_company_matcher_prefers_llm_selection(tmp_path):
    companies = tmp_path / "companies.json"
    companies.write_text(
        '[{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp", "ACME"]}]',
        encoding="utf-8",
    )

    engine = init_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    matcher = CompanyMatcher(SessionLocal(), str(companies), llm_client=FakeLLMClient())

    matches = matcher.match_companies(SAMPLE_ARTICLE_1.article.text)

    assert len(matches) == 1
    assert matches[0].company_name == "Acme Corp"
    assert matches[0].ticker == "ACME"
    assert matches[0].confidence == 0.97


def test_person_extractor_uses_llm_selection():
    extractor = PersonExtractor(llm_client=FakeLLMClient())

    people = extractor.extract_people(SAMPLE_ARTICLE_1, ["fraud", "money laundering"])

    assert len(people) == 1
    assert people[0].name == "John Smith"
    assert people[0].role == "ceo"


def test_connection_extractor_uses_llm_selection():
    extractor = ConnectionExtractor(llm_client=FakeLLMClient())

    connections = extractor.extract_connections(
        SAMPLE_ARTICLE_1,
        ["Acme Corp", "Beta Bank"],
        [],
        [],
    )

    assert len(connections) == 1
    assert connections[0].connection_type == "business_relationship"
    assert connections[0].entity_1_name == "Acme Corp"
    assert connections[0].entity_2_name == "Beta Bank"
