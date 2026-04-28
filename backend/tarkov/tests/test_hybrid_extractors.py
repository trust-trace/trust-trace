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


def test_company_matcher_prefers_llm_selection():
    from tarkov.database.models import Firm, FirmAlias

    engine = init_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    firm = Firm(full_name="Acme Corp", country="PL", market_ticker="ACME")
    db.add(firm)
    db.flush()
    db.add(FirmAlias(firm_id=firm.id, alias="Acme Corp", alias_type="name", confidence=1.0, is_primary=True))
    db.add(FirmAlias(firm_id=firm.id, alias="ACME", alias_type="ticker", confidence=1.0))
    db.flush()

    matcher = CompanyMatcher(db, llm_client=FakeLLMClient())

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
