"""Seed Postgres and Neo4j with realistic mock data for TrustWeb testing.

Simulates the output of the Tarkov extraction pipeline: firms, events
(classical/people/connection), sources, persons, and connection entities.

Usage:
    cd backend && .venv/bin/python -m scripts.seed_mock_data
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from tarkov.database.models import (
    ConnectionEntity,
    Event,
    Firm,
    FirmAlias,
    Person,
    PersonEvent,
    Source,
)
from tarkov.database.session import Base, SessionLocal, init_engine, init_neo4j, get_neo4j_session

PG_URL = "postgresql+psycopg2://trusttrace:trusttrace@localhost:5432/trusttrace_db"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "trusttrace"


def _uuid() -> str:
    return str(uuid.uuid4())


def _days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


def _years_ago(y: float) -> datetime:
    return datetime.utcnow() - timedelta(days=int(y * 365.25))


def create_pg_tables(engine):
    """Create all ORM tables + extra raw-SQL tables not in the ORM."""
    Base.metadata.create_all(bind=engine)

    extra_ddl = [
        """
        CREATE TABLE IF NOT EXISTS reputation_score (
            id              SERIAL PRIMARY KEY,
            firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            score           DECIMAL(6,2) NOT NULL,
            delta           DECIMAL(6,2),
            trigger_event_id VARCHAR(36) REFERENCES event(unique_id) ON DELETE SET NULL,
            calculated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trustweb_score (
            id              SERIAL PRIMARY KEY,
            firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            score           DECIMAL(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
            explanation     TEXT,
            node_count      INT,
            edge_count      INT,
            max_depth_used  INT,
            computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS firm_score_timeline (
            id              SERIAL PRIMARY KEY,
            firm_id         INT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            run_id          UUID NOT NULL,
            bucket_index    SMALLINT NOT NULL,
            bucket_start    TIMESTAMP NOT NULL,
            bucket_end      TIMESTAMP NOT NULL,
            score           INT NOT NULL,
            risk            VARCHAR(10) NOT NULL,
            event_count     INT NOT NULL DEFAULT 0,
            keywords        TEXT NOT NULL DEFAULT '[]',
            computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, bucket_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trustweb_score_timeline (
            id              SERIAL PRIMARY KEY,
            firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            run_id          UUID NOT NULL,
            bucket_index    SMALLINT NOT NULL,
            bucket_start    TIMESTAMP NOT NULL,
            bucket_end      TIMESTAMP NOT NULL,
            score           DECIMAL(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
            node_count      INT,
            edge_count      INT,
            max_depth_used  INT,
            computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, bucket_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trustweb_run (
            run_id          UUID PRIMARY KEY,
            firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            explanation     TEXT,
            computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pipeline_run (
            id              UUID PRIMARY KEY,
            query           TEXT NOT NULL,
            status          VARCHAR(30) NOT NULL DEFAULT 'created',
            phase           VARCHAR(30) NOT NULL DEFAULT 'created',
            article_target  INT NOT NULL DEFAULT 30,
            articles_scraped  INT NOT NULL DEFAULT 0,
            articles_processed INT NOT NULL DEFAULT 0,
            firm_ids        TEXT NOT NULL DEFAULT '[]',
            final_scores    TEXT NOT NULL DEFAULT '{}',
            error           TEXT,
            created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at    TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS final_score_timeline (
            id              SERIAL PRIMARY KEY,
            firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
            run_id          UUID NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
            bucket_index    SMALLINT NOT NULL,
            bucket_start    TIMESTAMP NOT NULL,
            bucket_end      TIMESTAMP NOT NULL,
            eem_score       DECIMAL(5,2),
            trustweb_score  DECIMAL(4,3),
            nsa_score       DECIMAL(4,3),
            final_score     DECIMAL(4,3) NOT NULL,
            risk_level      VARCHAR(10) NOT NULL,
            computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, firm_id, bucket_index)
        )
        """,
    ]
    with engine.connect() as conn:
        for ddl in extra_ddl:
            conn.execute(text(ddl))
        conn.commit()


def drop_all(engine):
    """Drop everything so we can re-seed cleanly."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS final_score_timeline CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS pipeline_run CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS trustweb_run CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS trustweb_score_timeline CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS firm_score_timeline CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS trustweb_score CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS reputation_score CASCADE"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)


def seed_postgres(session) -> dict:
    """Insert mock data via ORM. Returns a mapping of created IDs."""
    ids: dict = {}

    # ── Firms ──────────────────────────────────────────────────────────────

    firms = [
        Firm(full_name="Orion Capital Group Sp. z o.o.", nip="5261234567", krs="0000112233", country="PL",
             founded_at=_years_ago(8)),
        Firm(full_name="Baltic Shell Trading Ltd.", nip="7891234560", krs="0000445566", country="PL",
             founded_at=_years_ago(6)),
        Firm(full_name="Nordica Finance AG", country="CH",
             founded_at=_years_ago(12)),
        Firm(full_name="Vistula Logistics Sp. z o.o.", nip="6661234569", krs="0000778899", country="PL",
             founded_at=_years_ago(5)),
        Firm(full_name="Amber Consulting GmbH", country="DE",
             founded_at=_years_ago(3)),
    ]
    session.add_all(firms)
    session.flush()

    firm_ids = [f.id for f in firms]
    ids["firms"] = firm_ids
    print(f"  Created {len(firms)} firms: {firm_ids}")

    # ── Firm Aliases ───────────────────────────────────────────────────────

    session.add_all([
        FirmAlias(firm_id=firm_ids[0], alias="Orion Capital", alias_type="short_name", confidence=0.95),
        FirmAlias(firm_id=firm_ids[0], alias="OCG", alias_type="abbreviation", confidence=0.90),
        FirmAlias(firm_id=firm_ids[1], alias="Baltic Shell", alias_type="short_name", confidence=0.92),
    ])
    session.flush()

    # ── Classical Events ───────────────────────────────────────────────────

    classical_events = [
        Event(
            unique_id=_uuid(), firm_id=firm_ids[0],
            title="Orion Capital linked to suspected money laundering scheme in Warsaw",
            event_type="money_laundering_allegation", event_category="classical",
            risk_level=8, occurred_at=_days_ago(180), extraction_confidence=0.87,
            source_text_quote="Investigators allege Orion Capital Group funneled approximately €2.3M through a network of shell companies based in Cyprus and Malta.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[0],
            title="KNF investigation into Orion Capital regulatory compliance",
            event_type="regulatory_investigation", event_category="classical",
            risk_level=6, occurred_at=_days_ago(540), extraction_confidence=0.92,
            source_text_quote="Poland's Financial Supervision Authority (KNF) has opened a formal investigation into Orion Capital Group's compliance with AML directives.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[1],
            title="Baltic Shell Trading sanctioned by EU for embargo violations",
            event_type="sanctions_violation", event_category="classical",
            risk_level=9, occurred_at=_days_ago(90), extraction_confidence=0.95,
            source_text_quote="The European Council added Baltic Shell Trading Ltd. to the sanctions list for alleged violations of trade restrictions on dual-use goods.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[2],
            title="Nordica Finance AG subject of Swiss FINMA inquiry",
            event_type="regulatory_investigation", event_category="classical",
            risk_level=5, occurred_at=_days_ago(900), extraction_confidence=0.78,
            source_text_quote="FINMA has requested documents from Nordica Finance AG regarding suspicious transaction patterns with Eastern European counterparties.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[3],
            title="Vistula Logistics cleared in customs fraud probe",
            event_type="customs_fraud", event_category="classical",
            risk_level=3, occurred_at=_days_ago(400), extraction_confidence=0.85,
            source_text_quote="Vistula Logistics was cleared of customs fraud allegations after a 6-month investigation by Polish authorities.",
        ),
    ]
    session.add_all(classical_events)
    session.flush()

    # ── People Events ──────────────────────────────────────────────────────

    people_events = [
        Event(
            unique_id=_uuid(), firm_id=firm_ids[0],
            title="Jan Kowalski identified as beneficial owner of Orion Capital",
            event_type="beneficial_ownership", event_category="people",
            risk_level=7, occurred_at=_days_ago(730), extraction_confidence=0.88,
            source_text_quote="Records show Jan Kowalski holds 65% beneficial ownership of Orion Capital Group through a layered holding structure.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[1],
            title="Marek Nowak named as director of Baltic Shell",
            event_type="director_appointment", event_category="people",
            risk_level=4, occurred_at=_days_ago(1100), extraction_confidence=0.93,
            source_text_quote="Marek Nowak was appointed as managing director of Baltic Shell Trading Ltd.",
        ),
    ]
    session.add_all(people_events)
    session.flush()

    # ── Connection Events ──────────────────────────────────────────────────

    connection_events = [
        Event(
            unique_id=_uuid(), firm_id=firm_ids[0],
            title="Orion Capital and Baltic Shell share director Marek Nowak",
            event_type="shared_director_discovery", event_category="connection",
            risk_level=7, occurred_at=_days_ago(365), extraction_confidence=0.91,
            source_text_quote="Company registry filings reveal Marek Nowak serves as director at both Orion Capital Group and Baltic Shell Trading.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[0],
            title="Orion Capital has business relationship with Nordica Finance",
            event_type="business_relationship_discovery", event_category="connection",
            risk_level=6, occurred_at=_days_ago(600), extraction_confidence=0.83,
            source_text_quote="Financial transaction records indicate regular wire transfers between Orion Capital Group and Nordica Finance AG totaling CHF 4.7M over 18 months.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[1],
            title="Baltic Shell linked to Vistula Logistics through joint venture",
            event_type="activity_link_discovery", event_category="connection",
            risk_level=4, occurred_at=_days_ago(800), extraction_confidence=0.79,
            source_text_quote="Baltic Shell Trading and Vistula Logistics jointly operate a bonded warehouse in Gdańsk.",
        ),
        Event(
            unique_id=_uuid(), firm_id=firm_ids[2],
            title="Nordica Finance and Amber Consulting share beneficial owner",
            event_type="shared_beneficial_owner_discovery", event_category="connection",
            risk_level=5, occurred_at=_days_ago(1500), extraction_confidence=0.76,
            source_text_quote="Swiss corporate registry data shows Hans Weber listed as beneficial owner of both Nordica Finance AG and Amber Consulting GmbH.",
        ),
    ]
    session.add_all(connection_events)
    session.flush()

    # ── Sources (one per event) ────────────────────────────────────────────

    all_events = classical_events + people_events + connection_events
    source_urls = [
        "https://reuters.com/article/orion-capital-money-laundering-2026",
        "https://knf.gov.pl/komunikaty/orion-capital-investigation",
        "https://eucouncil.europa.eu/sanctions/baltic-shell-trading",
        "https://finma.ch/en/news/nordica-finance-inquiry",
        "https://biz.gazeta.pl/vistula-logistics-cleared",
        "https://krs.gov.pl/records/orion-beneficial-owner",
        "https://krs.gov.pl/records/baltic-shell-director",
        "https://onet.pl/biznes/orion-baltic-shell-shared-director",
        "https://swissinfo.ch/orion-nordica-finance-transfers",
        "https://biz.gazeta.pl/baltic-vistula-joint-venture",
        "https://zefix.ch/nordica-amber-beneficial-owner",
    ]
    for i, evt in enumerate(all_events):
        url = source_urls[i] if i < len(source_urls) else f"https://example.com/article/{i}"
        session.add(Source(
            event_id=evt.unique_id,
            url=url,
            title=f"Source article: {evt.title[:60]}",
            source_type="news_article",
            source_category="article",
            credibility=round(0.7 + (i % 3) * 0.1, 2),
        ))
    session.flush()

    # ── Persons ────────────────────────────────────────────────────────────

    persons = [
        Person(name="Jan Kowalski", role="beneficial_owner",
               description="Polish businessman, beneficial owner of Orion Capital Group",
               firm_id=firm_ids[0]),
        Person(name="Marek Nowak", role="director",
               description="Managing director at Baltic Shell Trading, also serves on Orion Capital board",
               firm_id=firm_ids[1]),
        Person(name="Hans Weber", role="beneficial_owner",
               description="Swiss national, beneficial owner of Nordica Finance and Amber Consulting",
               firm_id=firm_ids[2]),
        Person(name="Anna Wiśniewska", role="compliance_officer",
               description="Chief compliance officer at Orion Capital Group",
               firm_id=firm_ids[0]),
    ]
    session.add_all(persons)
    session.flush()

    person_ids = [p.id for p in persons]
    ids["persons"] = person_ids
    print(f"  Created {len(persons)} persons: {person_ids}")

    # ── Person-Event links ─────────────────────────────────────────────────

    session.add_all([
        PersonEvent(person_id=person_ids[0], event_id=people_events[0].unique_id,
                    role_in_event="beneficial_owner", confidence=0.88),
        PersonEvent(person_id=person_ids[1], event_id=people_events[1].unique_id,
                    role_in_event="director", confidence=0.93),
        PersonEvent(person_id=person_ids[3], event_id=people_events[0].unique_id,
                    role_in_event="mentioned", confidence=0.65),
    ])
    session.flush()

    # ── Connection Entities ────────────────────────────────────────────────

    session.add_all([
        ConnectionEntity(
            connection_event_id=connection_events[0].unique_id,
            connection_type="shared_director",
            entity_1_type="company", entity_1_id=str(firm_ids[0]),
            entity_1_name="Orion Capital Group Sp. z o.o.",
            entity_2_type="company", entity_2_id=str(firm_ids[1]),
            entity_2_name="Baltic Shell Trading Ltd.",
            relationship_description="Both companies share Marek Nowak as a director per KRS filings",
            confidence=0.91,
        ),
        ConnectionEntity(
            connection_event_id=connection_events[1].unique_id,
            connection_type="business_relationship",
            entity_1_type="company", entity_1_id=str(firm_ids[0]),
            entity_1_name="Orion Capital Group Sp. z o.o.",
            entity_2_type="company", entity_2_id=str(firm_ids[2]),
            entity_2_name="Nordica Finance AG",
            relationship_description="Regular wire transfers totaling CHF 4.7M over 18 months",
            confidence=0.83,
        ),
        ConnectionEntity(
            connection_event_id=connection_events[2].unique_id,
            connection_type="activity_link",
            entity_1_type="company", entity_1_id=str(firm_ids[1]),
            entity_1_name="Baltic Shell Trading Ltd.",
            entity_2_type="company", entity_2_id=str(firm_ids[3]),
            entity_2_name="Vistula Logistics Sp. z o.o.",
            relationship_description="Joint operation of bonded warehouse in Gdańsk",
            confidence=0.79,
        ),
        ConnectionEntity(
            connection_event_id=connection_events[3].unique_id,
            connection_type="shared_beneficial_owner",
            entity_1_type="company", entity_1_id=str(firm_ids[2]),
            entity_1_name="Nordica Finance AG",
            entity_2_type="company", entity_2_id=str(firm_ids[4]),
            entity_2_name="Amber Consulting GmbH",
            relationship_description="Hans Weber listed as beneficial owner of both entities in Swiss corporate registry",
            confidence=0.76,
        ),
        ConnectionEntity(
            connection_event_id=connection_events[0].unique_id,
            connection_type="shared_director",
            entity_1_type="person", entity_1_id=str(person_ids[1]),
            entity_1_name="Marek Nowak",
            entity_2_type="company", entity_2_id=str(firm_ids[0]),
            entity_2_name="Orion Capital Group Sp. z o.o.",
            relationship_description="Marek Nowak serves as director at Orion Capital Group",
            confidence=0.93,
        ),
    ])
    session.flush()

    # ── Reputation Scores ──────────────────────────────────────────────────

    reputation_data = [
        (firm_ids[0], 0.72, -0.15),
        (firm_ids[1], 0.85, -0.20),
        (firm_ids[2], 0.45, -0.05),
        (firm_ids[3], 0.18,  0.10),
        (firm_ids[4], 0.30,  0.00),
    ]
    for fid, score, delta in reputation_data:
        session.execute(text(
            "INSERT INTO reputation_score (firm_id, score, delta) "
            "VALUES (:firm_id, :score, :delta)"
        ), {"firm_id": fid, "score": score, "delta": delta})

    session.commit()

    ids["events"] = {
        "classical": [e.unique_id for e in classical_events],
        "people": [e.unique_id for e in people_events],
        "connection": [e.unique_id for e in connection_events],
    }
    return ids


def clear_neo4j():
    """Wipe all Neo4j nodes and relationships."""
    with get_neo4j_session() as g:
        g.run("MATCH (n) DETACH DELETE n")
    print("  Neo4j cleared")


def seed_neo4j_constraints():
    """Create uniqueness constraints for Neo4j."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
    ]
    with get_neo4j_session() as g:
        for c in constraints:
            g.run(c)
    print("  Neo4j constraints created")


def main():
    print("=" * 60)
    print("TrustWeb Mock Data Seeder")
    print("=" * 60)

    print("\n[1/5] Initializing database connections...")
    engine = init_engine(PG_URL)
    init_neo4j(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    print("\n[2/5] Dropping existing tables (clean slate)...")
    drop_all(engine)
    print("  Done")

    print("\n[3/5] Creating Postgres tables...")
    create_pg_tables(engine)
    print("  Tables ready")

    session = SessionLocal()
    try:
        print("\n[4/5] Seeding Postgres with mock data...")
        ids = seed_postgres(session)

        n_events = sum(len(v) for v in ids["events"].values())
        print(f"\n  Summary:")
        print(f"    Firms:               {len(ids['firms'])}")
        print(f"    Events (total):      {n_events}")
        print(f"      Classical:         {len(ids['events']['classical'])}")
        print(f"      People:            {len(ids['events']['people'])}")
        print(f"      Connection:        {len(ids['events']['connection'])}")
        print(f"    Persons:             {len(ids['persons'])}")

        print("\n[5/5] Preparing Neo4j...")
        clear_neo4j()
        seed_neo4j_constraints()
        print("  Neo4j ready (graph will be built by trust_web)")

        print("\n" + "=" * 60)
        print("Seeding complete!")
        print(f"Target firm for scoring: ID={ids['firms'][0]} (Orion Capital Group)")
        print("=" * 60)
    finally:
        session.close()


if __name__ == "__main__":
    main()
