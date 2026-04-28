"""Reset Postgres and Neo4j, seed sample graph data, and rebuild the graph."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from eem.database.models import EventEnrichment, FirmScore
from eem.database.session import Base as EemBase
from tarkov.config import Config
from tarkov.database.models import (
    ConnectionEntity,
    Event,
    Firm,
    Person,
    PersonEvent,
    Source,
)
from tarkov.database.session import (
    SessionLocal,
    create_all,
    get_engine,
    get_neo4j_session,
    init_engine,
    init_neo4j,
)
from trust_web.config import TrustWebConfig
from trust_web.graph.builder import build_graph_for_firm


def _clear_postgres(session) -> None:
    for model in (
        EventEnrichment,
        FirmScore,
        PersonEvent,
        ConnectionEntity,
        Source,
        Event,
        Person,
        Firm,
    ):
        session.query(model).delete()
    session.commit()


def _clear_neo4j() -> None:
    with get_neo4j_session() as neo4j_session:
        neo4j_session.run("MATCH (n) DETACH DELETE n")


def _seed_postgres(session) -> list[int]:
    acme = Firm(full_name="Acme Holdings S.A.", nip="1234567890", country="PL")
    beta = Firm(full_name="Beta Logistics Sp. z o.o.", nip="9876543210", country="PL")
    session.add_all([acme, beta])
    session.flush()

    session.add_all(
        [
            FirmScore(
                firm_id=acme.id,
                score=38,
                risk="high",
                trend=-6,
                score_history="[61, 54, 46, 38]",
                keywords='["aml", "investigation", "shell company"]',
                computed_at=datetime(2026, 4, 28, 10, 0, 0),
            ),
            FirmScore(
                firm_id=beta.id,
                score=67,
                risk="medium",
                trend=-2,
                score_history="[72, 70, 69, 67]",
                keywords='["shared director", "counterparty"]',
                computed_at=datetime(2026, 4, 28, 10, 0, 0),
            ),
        ]
    )

    director = Person(
        name="Jan Kowalski",
        role="Board Member",
        description="Serves on both companies' supervisory structures.",
        firm_id=acme.id,
    )
    compliance = Person(
        name="Anna Nowak",
        role="Compliance Officer",
        description="Mentioned in the investigation reporting.",
        firm_id=beta.id,
    )
    session.add_all([director, compliance])
    session.flush()

    event_people = Event(
        unique_id="evt-people-1",
        firm_id=acme.id,
        title="Board overlap uncovered",
        event_type="board_overlap",
        event_category="people",
        risk_level=6,
        occurred_at=datetime(2026, 4, 25, 9, 0, 0),
        source_text_quote="Jan Kowalski appears in management records for both firms.",
    )
    event_connection = Event(
        unique_id="evt-conn-1",
        firm_id=acme.id,
        title="Commercial ties between Acme and Beta",
        event_type="commercial_relationship",
        event_category="connection",
        risk_level=7,
        occurred_at=datetime(2026, 4, 26, 8, 30, 0),
        source_text_quote="Documents describe a repeated service relationship between the two firms.",
    )
    event_classical = Event(
        unique_id="evt-risk-1",
        firm_id=beta.id,
        title="Beta named in AML review",
        event_type="aml_review",
        event_category="classical",
        risk_level=8,
        occurred_at=datetime(2026, 4, 27, 7, 45, 0),
        source_text_quote="The regulator requested additional AML documentation from Beta Logistics.",
    )
    session.add_all([event_people, event_connection, event_classical])

    session.add_all(
        [
            Source(
                event_id="evt-people-1",
                url="https://example.com/board-overlap",
                title="Board overlap uncovered",
                content="Corporate registry records show Jan Kowalski tied to both Acme and Beta.",
                source_category="article",
                source_type="original",
                published_at=datetime(2026, 4, 25, 10, 0, 0),
                credibility=0.8,
            ),
            Source(
                event_id="evt-conn-1",
                url="https://example.com/commercial-ties",
                title="Commercial ties between Acme and Beta",
                content="Leaked invoices suggest a long-running business relationship between the companies.",
                source_category="article",
                source_type="original",
                published_at=datetime(2026, 4, 26, 11, 0, 0),
                credibility=0.85,
            ),
            Source(
                event_id="evt-risk-1",
                url="https://example.com/aml-review",
                title="Beta named in AML review",
                content="Beta Logistics was referenced during an anti-money-laundering review.",
                source_category="article",
                source_type="original",
                published_at=datetime(2026, 4, 27, 9, 0, 0),
                credibility=0.92,
            ),
        ]
    )

    session.add_all(
        [
            PersonEvent(
                person_id=director.id,
                event_id="evt-people-1",
                role_in_event="shared_director",
                confidence=0.95,
            ),
            PersonEvent(
                person_id=compliance.id,
                event_id="evt-risk-1",
                role_in_event="mentioned_person",
                confidence=0.72,
            ),
        ]
    )

    session.add(
        ConnectionEntity(
            connection_event_id="evt-conn-1",
            connection_type="business_relationship",
            entity_1_type="company",
            entity_1_id=str(acme.id),
            entity_1_name=acme.full_name,
            entity_2_type="company",
            entity_2_id=str(beta.id),
            entity_2_name=beta.full_name,
            relationship_description="Repeated logistics services and invoice flows.",
            confidence=0.88,
        )
    )

    session.add_all(
        [
            EventEnrichment(
                event_id="evt-conn-1",
                sentiment=-0.6,
                impact=-3.1,
                source_tier="tier-1",
                keywords='["invoice", "logistics", "relationship"]',
                excerpt="The article links Acme and Beta through repeated service contracts.",
                entities='["Acme Holdings S.A.", "Beta Logistics Sp. z o.o."]',
                model_used="seed-script",
                enriched_at=datetime(2026, 4, 28, 10, 0, 0),
            ),
            EventEnrichment(
                event_id="evt-risk-1",
                sentiment=-0.8,
                impact=-4.2,
                source_tier="tier-1",
                keywords='["aml", "review", "regulator"]',
                excerpt="Beta Logistics was drawn into an AML review.",
                entities='["Beta Logistics Sp. z o.o.", "regulator"]',
                model_used="seed-script",
                enriched_at=datetime(2026, 4, 28, 10, 0, 0),
            ),
        ]
    )

    session.commit()
    return [acme.id, beta.id]


async def _rebuild_graph(session, firm_ids: list[int], config: TrustWebConfig) -> None:
    for firm_id in firm_ids:
        await build_graph_for_firm(firm_id, session, config, force_rescore=True)


def main() -> None:
    tarkov_config = Config.from_env()
    trustweb_config = TrustWebConfig.from_env()

    init_engine(tarkov_config.database_url)
    create_all()
    EemBase.metadata.create_all(bind=get_engine())
    init_neo4j(
        tarkov_config.neo4j_uri,
        tarkov_config.neo4j_user,
        tarkov_config.neo4j_password,
    )

    firm_ids: list[int] = []
    session = SessionLocal()
    try:
        _clear_postgres(session)
        _clear_neo4j()
        firm_ids = _seed_postgres(session)
        asyncio.run(_rebuild_graph(session, firm_ids, trustweb_config))
    finally:
        session.close()

    print(f"Seeded Postgres and Neo4j for firms: {', '.join(map(str, firm_ids))}")


if __name__ == "__main__":
    main()
