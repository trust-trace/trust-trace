from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from eem.database.models import Base as EemBase, EventEnrichment, FirmScore
from tarkov.config import Config
from tarkov.database.models import (
    Base as TarkovBase,
    ConnectionEntity,
    Event,
    Firm,
    Person,
    PersonEvent,
    Source,
)
from tarkov.frontend_graph_api import FrontendGraphService


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TarkovBase.metadata.create_all(bind=engine)
    EemBase.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    return factory()


def build_config() -> Config:
    return Config(
        database_url="sqlite+pysqlite:///:memory:",
        log_level="INFO",
        llm_provider="none",
        llm_api_key="",
        llm_model="gpt-4o-mini",
        article_input_source="jsonl",
        article_input_path="",
        company_reference_path="",
        keywords_file_path="",
        dead_letter_path="",
        api_host="127.0.0.1",
        api_port=8081,
        enable_stage3_dispatch=False,
        event_classifier_url="",
        nsa_url="",
        trustweb_url="",
    )


def test_list_companies_shapes_frontend_payload(monkeypatch):
    session = build_session()
    session.add(
        Firm(
            id=1,
            full_name="Acme Holdings S.A.",
            nip="1234567890",
            country="PL",
        )
    )
    session.add(
        FirmScore(
            firm_id=1,
            score=82,
            risk="low",
            trend=4,
            score_history="[70, 76, 82]",
            keywords='["fraud", "audit"]',
            computed_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.add(
        Event(
            unique_id="evt-1",
            firm_id=1,
            title="Acme investigation update",
            event_type="investigation",
            event_category="classical",
            risk_level=7,
            occurred_at=datetime(2026, 4, 27, 10, 0, 0),
        )
    )
    session.add(
        Source(
            event_id="evt-1",
            url="https://example.com/acme",
            title="Acme investigation update",
            source_category="article",
            published_at=datetime(2026, 4, 27, 11, 0, 0),
        )
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_nodes",
        lambda: [{"company_id": "1", "name": "Acme Holdings S.A."}],
    )

    companies = service.list_companies(session)

    assert companies == [
        {
            "id": "acme-holdings",
            "name": "Acme Holdings S.A.",
            "short": "Acme Holdings",
            "nip": "1234567890",
            "sector": "Unknown",
            "score": 82,
            "trend": 4,
            "risk": "low",
            "articles": 1,
            "lastUpdate": "2026-04-27T11:00:00",
            "history": [70, 76, 82],
            "keywords": ["fraud", "audit"],
        }
    ]


def test_list_companies_falls_back_to_sql_firms_when_graph_is_empty(monkeypatch):
    session = build_session()
    session.add(
        Firm(
            id=1,
            full_name="Acme Holdings S.A.",
            nip="1234567890",
            country="PL",
        )
    )
    session.add(
        FirmScore(
            firm_id=1,
            score=82,
            risk="low",
            trend=4,
            score_history="[70, 76, 82]",
            keywords='["fraud", "audit"]',
            computed_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.add(
        Event(
            unique_id="evt-1",
            firm_id=1,
            title="Acme investigation update",
            event_type="investigation",
            event_category="classical",
            risk_level=7,
            occurred_at=datetime(2026, 4, 27, 10, 0, 0),
        )
    )
    session.add(
        Source(
            event_id="evt-1",
            url="https://example.com/acme",
            title="Acme investigation update",
            source_category="article",
            published_at=datetime(2026, 4, 27, 11, 0, 0),
        )
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_nodes", lambda: [])

    companies = service.list_companies(session)

    assert companies == [
        {
            "id": "acme-holdings",
            "name": "Acme Holdings S.A.",
            "short": "Acme Holdings",
            "nip": "1234567890",
            "sector": "Unknown",
            "score": 82,
            "trend": 4,
            "risk": "low",
            "articles": 1,
            "lastUpdate": "2026-04-27T11:00:00",
            "history": [70, 76, 82],
            "keywords": ["fraud", "audit"],
        }
    ]


def test_list_companies_merges_partial_graph_rows_with_sql_firms(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", country="PL"),
            Firm(id=2, full_name="Beta Logistics Sp. z o.o.", country="PL"),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_nodes",
        lambda: [{"company_id": "1", "name": "Acme Holdings S.A."}],
    )

    companies = service.list_companies(session)

    assert [company["id"] for company in companies] == [
        "acme-holdings",
        "beta-logistics",
    ]


def test_list_relations_maps_graph_edges_to_frontend_payload(monkeypatch):
    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_relations",
        lambda: [
            {
                "source_company_id": "1",
                "source_name": "Acme Holdings S.A.",
                "target_company_id": "2",
                "target_name": "Beta Logistics Sp. z o.o.",
                "connection_type": "board_overlap",
                "description": "Shared supervisory board member",
                "intensity": 0.9,
            },
            {
                "source_company_id": "2",
                "source_name": "Beta Logistics Sp. z o.o.",
                "target_company_id": "1",
                "target_name": "Acme Holdings S.A.",
                "connection_type": "commercial_relationship",
                "description": "Commercial cooperation",
                "intensity": 0.2,
            },
        ],
    )

    relations = service.list_relations(build_session())

    assert relations == [
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "beta-logistics",
            "type": "business",
            "label": "Commercial cooperation",
        },
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "beta-logistics",
            "type": "person",
            "label": "Shared supervisory board member",
        },
    ]


def test_list_relations_falls_back_to_sql_connection_entities(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", country="PL"),
            Firm(id=2, full_name="Beta Logistics Sp. z o.o.", country="PL"),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Shared board investigation",
                event_type="shared_director",
                event_category="classical",
                risk_level=6,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
            ConnectionEntity(
                connection_event_id="evt-1",
                connection_type="shared_director",
                entity_1_type="company",
                entity_1_id="1",
                entity_1_name="Acme Holdings S.A.",
                entity_2_type="company",
                entity_2_id="2",
                entity_2_name="Beta Logistics Sp. z o.o.",
                relationship_description="Both companies share Marek Nowak as a director",
                confidence=0.9,
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_relations", lambda: [])

    relations = service.list_relations(session)

    assert relations == [
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "beta-logistics",
            "type": "person",
            "label": "Both companies share Marek Nowak as a director",
        }
    ]


def test_list_relations_merges_partial_graph_rows_with_sql_connections(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", country="PL"),
            Firm(id=2, full_name="Beta Logistics Sp. z o.o.", country="PL"),
            Firm(id=3, full_name="Gamma Metals S.A.", country="PL"),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Shared board investigation",
                event_type="shared_director",
                event_category="classical",
                risk_level=6,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
            ConnectionEntity(
                connection_event_id="evt-1",
                connection_type="shared_director",
                entity_1_type="company",
                entity_1_id="1",
                entity_1_name="Acme Holdings S.A.",
                entity_2_type="company",
                entity_2_id="2",
                entity_2_name="Beta Logistics Sp. z o.o.",
                relationship_description="Both companies share Marek Nowak as a director",
                confidence=0.9,
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_relations",
        lambda: [
            {
                "source_company_id": "1",
                "source_name": "Acme Holdings S.A.",
                "target_company_id": "3",
                "target_name": "Gamma Metals S.A.",
                "connection_type": "commercial_relationship",
                "description": "Commercial cooperation",
                "intensity": 0.2,
            }
        ],
    )

    relations = service.list_relations(session)

    assert relations == [
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "beta-logistics",
            "type": "person",
            "label": "Both companies share Marek Nowak as a director",
        },
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "gamma-metals",
            "type": "business",
            "label": "Commercial cooperation",
        },
    ]


def test_list_relations_prefers_richer_sql_label_for_overlapping_relation(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", country="PL"),
            Firm(id=2, full_name="Beta Logistics Sp. z o.o.", country="PL"),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Shared board investigation",
                event_type="shared_director",
                event_category="classical",
                risk_level=6,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
            ConnectionEntity(
                connection_event_id="evt-1",
                connection_type="shared_director",
                entity_1_type="company",
                entity_1_id="1",
                entity_1_name="Acme Holdings S.A.",
                entity_2_type="company",
                entity_2_id="2",
                entity_2_name="Beta Logistics Sp. z o.o.",
                relationship_description="Both companies share Marek Nowak as a director",
                confidence=0.2,
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_company_relations",
        lambda: [
            {
                "source_company_id": "1",
                "source_name": "Acme Holdings S.A.",
                "target_company_id": "2",
                "target_name": "Beta Logistics Sp. z o.o.",
                "connection_type": "shared_director",
                "description": "",
                "intensity": 0.9,
            }
        ],
    )

    relations = service.list_relations(session)

    assert relations == [
        {
            "sourceCompanyId": "acme-holdings",
            "targetCompanyId": "beta-logistics",
            "type": "person",
            "label": "Both companies share Marek Nowak as a director",
        }
    ]


def test_list_articles_returns_frontend_article_shape(monkeypatch):
    session = build_session()
    session.add(
        Firm(
            id=1,
            full_name="Acme Holdings S.A.",
            country="PL",
        )
    )
    session.add(
        Event(
            unique_id="evt-1",
            firm_id=1,
            title="Acme investigation update",
            event_type="investigation",
            event_category="classical",
            risk_level=8,
            occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            source_text_quote="Important investigation quote.",
        )
    )
    session.add(
        Source(
            event_id="evt-1",
            url="https://reuters.com/acme",
            title="Reuters reports on Acme",
            content="Detailed article body",
            source_category="article",
            published_at=datetime(2026, 4, 27, 9, 30, 0),
            credibility=0.9,
        )
    )
    session.add(
        EventEnrichment(
            event_id="evt-1",
            sentiment=-0.7,
            impact=-3.5,
            source_tier="tier-1",
            keywords='["aml", "investigation"]',
            excerpt="Short excerpt",
            entities='["Acme Holdings", "KNF"]',
            model_used="test-model",
            enriched_at=datetime(2026, 4, 27, 12, 0, 0),
        )
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_nodes", lambda: [])

    articles = service.list_articles(session, "acme-holdings")

    assert articles == [
        {
            "id": "evt-1",
            "headline": "Reuters reports on Acme",
            "source": "Reuters",
            "sourceTier": "tier-1",
            "date": "2026-04-27T09:30:00",
            "sentiment": -0.7,
            "impact": -3.5,
            "keywords": ["aml", "investigation"],
            "excerpt": "Short excerpt",
            "entities": ["Acme Holdings", "KNF"],
        }
    ]


def test_get_graph_enriches_company_person_and_event_nodes(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", nip="1234567890", country="PL"),
            Firm(id=2, full_name="Beta Logistics Sp. z o.o.", country="PL"),
            FirmScore(
                firm_id=1,
                score=82,
                risk="low",
                trend=4,
                score_history="[70, 76, 82]",
                keywords='["fraud", "audit"]',
                computed_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
            Person(
                id=10,
                name="Jan Kowalski",
                role="Board Member",
                description="Shared director",
                firm_id=1,
            ),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Acme investigation update",
                event_type="investigation",
                event_category="classical",
                risk_level=8,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
                source_text_quote="Important investigation quote.",
            ),
            Source(
                event_id="evt-1",
                url="https://reuters.com/acme",
                title="Reuters reports on Acme",
                content="Detailed article body",
                source_category="article",
                published_at=datetime(2026, 4, 27, 9, 30, 0),
                credibility=0.9,
            ),
            EventEnrichment(
                event_id="evt-1",
                sentiment=-0.7,
                impact=-3.5,
                source_tier="tier-1",
                keywords='["aml", "investigation"]',
                excerpt="Short excerpt",
                entities='["Acme Holdings", "KNF"]',
                model_used="test-model",
                enriched_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
            PersonEvent(
                person_id=10, event_id="evt-1", role_in_event="subject", confidence=0.9
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(
        service,
        "_query_graph_nodes",
        lambda firm_id, max_depth: [
            {
                "node": {"company_id": "1", "name": "Acme Holdings S.A."},
                "labels": ["Company"],
                "depth": 0,
            },
            {
                "node": {"person_id": "10", "name": "Jan Kowalski"},
                "labels": ["Person"],
                "depth": 1,
            },
            {
                "node": {
                    "event_id": "evt-1",
                    "title": "Acme investigation update",
                    "event_type": "investigation",
                    "risk_level": 8,
                },
                "labels": ["Event"],
                "depth": 1,
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "_query_graph_edges",
        lambda firm_id, max_depth: [
            {
                "relationship_type": "AFFILIATED_WITH",
                "source_labels": ["Company"],
                "source_node": {"company_id": "1"},
                "target_labels": ["Person"],
                "target_node": {"person_id": "10"},
                "connection_type": "",
                "intensity": None,
                "description": "",
                "source_url": "",
                "source_title": "",
            },
            {
                "relationship_type": "ABOUT",
                "source_labels": ["Company"],
                "source_node": {"company_id": "1"},
                "target_labels": ["Event"],
                "target_node": {"event_id": "evt-1"},
                "connection_type": "",
                "intensity": None,
                "description": "",
                "source_url": "https://reuters.com/acme",
                "source_title": "Reuters reports on Acme",
            },
        ],
    )

    graph = service.get_graph(session, "acme-holdings", max_depth=2)

    assert graph["rootId"] == "company:1"
    assert graph["nodes"] == [
        {
            "id": "company:1",
            "entityType": "Company",
            "entityId": "1",
            "depth": 0,
            "label": "Acme Holdings S.A.",
            "data": {
                "id": "acme-holdings",
                "name": "Acme Holdings S.A.",
                "short": "Acme Holdings",
                "nip": "1234567890",
                "country": "PL",
                "score": 82,
                "trend": 4,
                "risk": "low",
                "history": [70, 76, 82],
                "keywords": ["fraud", "audit"],
                "articles": 1,
                "lastUpdate": "2026-04-27T09:30:00",
            },
        },
        {
            "id": "event:evt-1",
            "entityType": "Event",
            "entityId": "evt-1",
            "depth": 1,
            "label": "Acme investigation update",
            "data": {
                "title": "Acme investigation update",
                "eventType": "investigation",
                "eventCategory": "classical",
                "riskLevel": 8,
                "risk": "high",
                "occurredAt": "2026-04-27T10:00:00",
                "companyId": "acme-holdings",
                "companyName": "Acme Holdings S.A.",
                "excerpt": "Short excerpt",
                "keywords": ["aml", "investigation"],
                "entities": ["Acme Holdings", "KNF"],
                "source": "Reuters",
                "sourceTitle": "Reuters reports on Acme",
                "sourceUrl": "https://reuters.com/acme",
            },
        },
        {
            "id": "person:10",
            "entityType": "Person",
            "entityId": "10",
            "depth": 1,
            "label": "Jan Kowalski",
            "data": {
                "name": "Jan Kowalski",
                "role": "Board Member",
                "description": "Shared director",
                "firmId": "acme-holdings",
                "firmName": "Acme Holdings S.A.",
                "eventCount": 1,
                "trustScore": 28,
                "risk": "high",
            },
        },
    ]
    assert graph["edges"] == [
        {
            "id": "company:1->event:evt-1:ABOUT:-",
            "source": "company:1",
            "target": "event:evt-1",
            "relationshipType": "ABOUT",
            "connectionType": "",
            "intensity": None,
            "label": "About",
            "sourceUrl": "https://reuters.com/acme",
            "sourceTitle": "Reuters reports on Acme",
        },
        {
            "id": "company:1->person:10:AFFILIATED_WITH:-",
            "source": "company:1",
            "target": "person:10",
            "relationshipType": "AFFILIATED_WITH",
            "connectionType": "",
            "intensity": None,
            "label": "Affiliated with",
            "sourceUrl": "",
            "sourceTitle": "",
        },
        {
            "id": "person:10->event:evt-1:INVOLVED_IN:subject",
            "source": "person:10",
            "target": "event:evt-1",
            "relationshipType": "INVOLVED_IN",
            "connectionType": "subject",
            "intensity": 0.9,
            "label": "Involved in",
            "sourceUrl": "https://reuters.com/acme",
            "sourceTitle": "Reuters reports on Acme",
        },
    ]


def test_get_graph_falls_back_to_graph_company_lookup_when_sql_firm_missing(
    monkeypatch,
):
    session = build_session()
    service = FrontendGraphService(build_config())

    monkeypatch.setattr(
        service,
        "_query_company_nodes",
        lambda: [{"company_id": "1", "name": "Acme Holdings S.A."}],
    )
    monkeypatch.setattr(
        service,
        "_query_graph_nodes",
        lambda firm_id, max_depth: [
            {
                "node": {"company_id": "1", "name": "Acme Holdings S.A."},
                "labels": ["Company"],
                "depth": 0,
            },
            {
                "node": {"person_id": "10", "name": "Jan Kowalski"},
                "labels": ["Person"],
                "depth": 1,
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "_query_graph_edges",
        lambda firm_id, max_depth: [
            {
                "relationship_type": "AFFILIATED_WITH",
                "source_labels": ["Company"],
                "source_node": {"company_id": "1"},
                "target_labels": ["Person"],
                "target_node": {"person_id": "10"},
                "connection_type": "",
                "intensity": None,
                "description": "",
                "source_url": "",
                "source_title": "",
            }
        ],
    )

    graph = service.get_graph(session, "acme-holdings", max_depth=2)

    assert graph["rootId"] == "company:1"
    assert graph["nodes"] == [
        {
            "id": "company:1",
            "entityType": "Company",
            "entityId": "1",
            "depth": 0,
            "label": "Acme Holdings S.A.",
            "data": {
                "id": "acme-holdings",
                "name": "Acme Holdings S.A.",
                "short": "Acme Holdings",
                "nip": "",
                "country": "",
                "score": 50,
                "trend": 0,
                "risk": "medium",
                "history": [50],
                "keywords": [],
                "articles": 0,
                "lastUpdate": "",
            },
        },
        {
            "id": "person:10",
            "entityType": "Person",
            "entityId": "10",
            "depth": 1,
            "label": "Jan Kowalski",
            "data": {
                "name": "Jan Kowalski",
                "role": "",
                "description": "",
                "firmId": "",
                "firmName": "",
                "eventCount": 0,
                "trustScore": 100,
                "risk": "low",
            },
        },
    ]
    assert graph["edges"] == [
        {
            "id": "company:1->person:10:AFFILIATED_WITH:-",
            "source": "company:1",
            "target": "person:10",
            "relationshipType": "AFFILIATED_WITH",
            "connectionType": "",
            "intensity": None,
            "label": "Affiliated with",
            "sourceUrl": "",
            "sourceTitle": "",
        }
    ]


def test_get_graph_falls_back_to_sql_entities_when_graph_is_empty(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", nip="1234567890", country="PL"),
            FirmScore(
                firm_id=1,
                score=82,
                risk="low",
                trend=4,
                score_history="[70, 76, 82]",
                keywords='["fraud", "audit"]',
                computed_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
            Person(
                id=10,
                name="Jan Kowalski",
                role="Board Member",
                description="Shared director",
                firm_id=1,
            ),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Acme investigation update",
                event_type="investigation",
                event_category="classical",
                risk_level=8,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
                source_text_quote="Important investigation quote.",
            ),
            Source(
                event_id="evt-1",
                url="https://reuters.com/acme",
                title="Reuters reports on Acme",
                content="Detailed article body",
                source_category="article",
                published_at=datetime(2026, 4, 27, 9, 30, 0),
                credibility=0.9,
            ),
            EventEnrichment(
                event_id="evt-1",
                sentiment=-0.7,
                impact=-3.5,
                source_tier="tier-1",
                keywords='["aml", "investigation"]',
                excerpt="Short excerpt",
                entities='["Acme Holdings", "KNF"]',
                model_used="test-model",
                enriched_at=datetime(2026, 4, 27, 12, 0, 0),
            ),
            PersonEvent(
                person_id=10, event_id="evt-1", role_in_event="subject", confidence=0.9
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_nodes", lambda: [])
    monkeypatch.setattr(service, "_query_graph_nodes", lambda firm_id, max_depth: [])
    monkeypatch.setattr(service, "_query_graph_edges", lambda firm_id, max_depth: [])

    graph = service.get_graph(session, "acme-holdings", max_depth=2)

    assert graph["rootId"] == "company:1"
    assert graph["nodes"] == [
        {
            "id": "company:1",
            "entityType": "Company",
            "entityId": "1",
            "depth": 0,
            "label": "Acme Holdings S.A.",
            "data": {
                "id": "acme-holdings",
                "name": "Acme Holdings S.A.",
                "short": "Acme Holdings",
                "nip": "1234567890",
                "country": "PL",
                "score": 82,
                "trend": 4,
                "risk": "low",
                "history": [70, 76, 82],
                "keywords": ["fraud", "audit"],
                "articles": 1,
                "lastUpdate": "2026-04-27T09:30:00",
            },
        },
        {
            "id": "event:evt-1",
            "entityType": "Event",
            "entityId": "evt-1",
            "depth": 1,
            "label": "Acme investigation update",
            "data": {
                "title": "Acme investigation update",
                "eventType": "investigation",
                "eventCategory": "classical",
                "riskLevel": 8,
                "risk": "high",
                "occurredAt": "2026-04-27T10:00:00",
                "companyId": "acme-holdings",
                "companyName": "Acme Holdings S.A.",
                "excerpt": "Short excerpt",
                "keywords": ["aml", "investigation"],
                "entities": ["Acme Holdings", "KNF"],
                "source": "Reuters",
                "sourceTitle": "Reuters reports on Acme",
                "sourceUrl": "https://reuters.com/acme",
            },
        },
        {
            "id": "person:10",
            "entityType": "Person",
            "entityId": "10",
            "depth": 1,
            "label": "Jan Kowalski",
            "data": {
                "name": "Jan Kowalski",
                "role": "Board Member",
                "description": "Shared director",
                "firmId": "acme-holdings",
                "firmName": "Acme Holdings S.A.",
                "eventCount": 1,
                "trustScore": 28,
                "risk": "high",
            },
        },
    ]
    assert graph["edges"] == [
        {
            "id": "company:1->event:evt-1:ABOUT:-",
            "source": "company:1",
            "target": "event:evt-1",
            "relationshipType": "ABOUT",
            "connectionType": "",
            "intensity": None,
            "label": "About",
            "sourceUrl": "https://reuters.com/acme",
            "sourceTitle": "Reuters reports on Acme",
        },
        {
            "id": "company:1->person:10:AFFILIATED_WITH:-",
            "source": "company:1",
            "target": "person:10",
            "relationshipType": "AFFILIATED_WITH",
            "connectionType": "",
            "intensity": None,
            "label": "Affiliated with",
            "sourceUrl": "",
            "sourceTitle": "",
        },
        {
            "id": "person:10->event:evt-1:INVOLVED_IN:subject",
            "source": "person:10",
            "target": "event:evt-1",
            "relationshipType": "INVOLVED_IN",
            "connectionType": "subject",
            "intensity": 0.9,
            "label": "Involved in",
            "sourceUrl": "https://reuters.com/acme",
            "sourceTitle": "Reuters reports on Acme",
        },
    ]


def test_get_graph_merges_sql_fallback_with_partial_graph_rows(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", nip="1234567890", country="PL"),
            Person(
                id=10,
                name="Jan Kowalski",
                role="Board Member",
                description="Shared director",
                firm_id=1,
            ),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Acme investigation update",
                event_type="investigation",
                event_category="classical",
                risk_level=8,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
            Source(
                event_id="evt-1",
                url="https://reuters.com/acme",
                title="Reuters reports on Acme",
                source_category="article",
                published_at=datetime(2026, 4, 27, 9, 30, 0),
            ),
            PersonEvent(
                person_id=10, event_id="evt-1", role_in_event="subject", confidence=0.9
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_nodes", lambda: [])
    monkeypatch.setattr(
        service,
        "_query_graph_nodes",
        lambda firm_id, max_depth: [
            {
                "node": {"company_id": "1", "name": "Acme Holdings S.A."},
                "labels": ["Company"],
                "depth": 0,
            }
        ],
    )
    monkeypatch.setattr(service, "_query_graph_edges", lambda firm_id, max_depth: [])

    graph = service.get_graph(session, "acme-holdings", max_depth=2)

    assert {node["id"] for node in graph["nodes"]} == {
        "company:1",
        "event:evt-1",
        "person:10",
    }
    assert {edge["id"] for edge in graph["edges"]} == {
        "company:1->event:evt-1:ABOUT:-",
        "company:1->person:10:AFFILIATED_WITH:-",
        "person:10->event:evt-1:INVOLVED_IN:subject",
    }


def test_get_graph_prefers_richer_sql_edge_fields_for_overlapping_edge(monkeypatch):
    session = build_session()
    session.add_all(
        [
            Firm(id=1, full_name="Acme Holdings S.A.", country="PL"),
            Event(
                unique_id="evt-1",
                firm_id=1,
                title="Acme investigation update",
                event_type="investigation",
                event_category="classical",
                risk_level=8,
                occurred_at=datetime(2026, 4, 27, 10, 0, 0),
            ),
            Source(
                event_id="evt-1",
                url="https://reuters.com/acme",
                title="Reuters reports on Acme",
                source_category="article",
                published_at=datetime(2026, 4, 27, 9, 30, 0),
            ),
        ]
    )
    session.commit()

    service = FrontendGraphService(build_config())
    monkeypatch.setattr(service, "_query_company_nodes", lambda: [])
    monkeypatch.setattr(
        service,
        "_query_graph_nodes",
        lambda firm_id, max_depth: [
            {
                "node": {"company_id": "1", "name": "Acme Holdings S.A."},
                "labels": ["Company"],
                "depth": 0,
            },
            {
                "node": {
                    "event_id": "evt-1",
                    "title": "Acme investigation update",
                    "event_type": "investigation",
                    "risk_level": 8,
                },
                "labels": ["Event"],
                "depth": 1,
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "_query_graph_edges",
        lambda firm_id, max_depth: [
            {
                "relationship_type": "ABOUT",
                "source_labels": ["Company"],
                "source_node": {"company_id": "1"},
                "target_labels": ["Event"],
                "target_node": {"event_id": "evt-1"},
                "connection_type": "",
                "intensity": None,
                "description": "",
                "source_url": "",
                "source_title": "",
            }
        ],
    )

    graph = service.get_graph(session, "acme-holdings", max_depth=2)

    assert graph["edges"] == [
        {
            "id": "company:1->event:evt-1:ABOUT:-",
            "source": "company:1",
            "target": "event:evt-1",
            "relationshipType": "ABOUT",
            "connectionType": "",
            "intensity": None,
            "label": "About",
            "sourceUrl": "https://reuters.com/acme",
            "sourceTitle": "Reuters reports on Acme",
        }
    ]
