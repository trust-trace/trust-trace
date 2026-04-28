"""Static Neo4j edge builder — creates graph edges from Postgres data.

Runs after each article ingestion to ensure the graph is immediately
queryable without waiting for TrustWeb's LLM-powered analysis.

Creates four edge types from existing Postgres data:
  ABOUT           Company → Event  (firm_id on event)
  AFFILIATED_WITH Company → Person (firm_id on person)
  INVOLVED_IN     Person  → Event  (person_event rows)
  CONNECTION      Any     → Any    (connection_entity rows)
"""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import (
    ConnectionEntity,
    Event,
    Firm,
    FirmAlias,
    Person,
    PersonEvent,
    Source,
)
from tarkov.database.session import get_neo4j_session

logger = logging.getLogger(__name__)


def build_edges_for_firm(firm_id: int, pg_session: Session) -> int:
    """Create Neo4j edges for a single firm from Postgres data.

    Returns the number of edges written.
    """
    edges_written = 0

    events = pg_session.scalars(
        select(Event).where(Event.firm_id == firm_id)
    ).all()

    if not events:
        return 0

    # ABOUT: Company → Event
    for event in events:
        _merge_about(str(firm_id), event.unique_id)
        edges_written += 1

    # AFFILIATED_WITH: Company → Person
    persons = pg_session.scalars(
        select(Person).where(Person.firm_id == firm_id)
    ).all()
    for person in persons:
        _merge_affiliated(str(firm_id), str(person.id), person.role or "")
        edges_written += 1

    # INVOLVED_IN: Person → Event
    event_ids = [e.unique_id for e in events]
    if event_ids:
        pe_links = pg_session.scalars(
            select(PersonEvent).where(PersonEvent.event_id.in_(event_ids))
        ).all()
        for link in pe_links:
            _merge_involved_in(
                str(link.person_id),
                str(link.event_id),
                link.role_in_event or "",
                link.confidence or 0.5,
            )
            edges_written += 1

    # CONNECTION: from connection_entity rows
    # These rows often have name-based IDs rather than integer PG IDs,
    # so we resolve them to real Neo4j node IDs where possible.
    firm_name_to_id = _build_firm_name_index(pg_session)
    person_name_to_id = _build_person_name_index(pg_session, firm_id)

    connection_events = [e for e in events if e.event_category == "connection"]
    for ce_event in connection_events:
        ce_rows = pg_session.scalars(
            select(ConnectionEntity).where(
                ConnectionEntity.connection_event_id == ce_event.unique_id
            )
        ).all()

        source = pg_session.scalars(
            select(Source).where(
                Source.event_id == ce_event.unique_id,
                Source.source_category == "article",
            ).limit(1)
        ).first()

        for ce in ce_rows:
            resolved_1 = _resolve_entity_id(
                ce.entity_1_type, ce.entity_1_id, ce.entity_1_name,
                firm_name_to_id, person_name_to_id,
            )
            resolved_2 = _resolve_entity_id(
                ce.entity_2_type, ce.entity_2_id, ce.entity_2_name,
                firm_name_to_id, person_name_to_id,
            )
            if resolved_1 is None or resolved_2 is None:
                continue

            label_a, id_prop_a, id_a = resolved_1
            label_b, id_prop_b, id_b = resolved_2

            _merge_connection(
                label_a, id_prop_a, id_a,
                label_b, id_prop_b, id_b,
                event_id=ce_event.unique_id,
                connection_type=ce.connection_type,
                intensity=ce.confidence or 0.5,
                description=ce.relationship_description or "",
                source_url=source.url if source else "",
                source_title=source.title if source and source.title else "",
                occurred_at=ce_event.occurred_at.isoformat() if ce_event.occurred_at else None,
            )
            edges_written += 1

    logger.info(
        "Static graph: wrote %d edges for firm %d (%d events, %d persons, %d connections)",
        edges_written, firm_id,
        len(events), len(persons), len(connection_events),
    )
    return edges_written


def build_edges_for_firms(firm_ids: Sequence[int], pg_session: Session) -> int:
    total = 0
    for firm_id in firm_ids:
        total += build_edges_for_firm(firm_id, pg_session)
    return total


# ── Neo4j write helpers ──────────────────────────────────────────────────

def _merge_about(firm_id: str, event_id: str) -> None:
    with get_neo4j_session() as g:
        g.run(
            "MATCH (c:Company {company_id: $firm_id}) "
            "MATCH (e:Event {event_id: $event_id}) "
            "MERGE (c)-[:ABOUT]->(e)",
            firm_id=firm_id,
            event_id=event_id,
        )


def _merge_affiliated(firm_id: str, person_id: str, role: str) -> None:
    with get_neo4j_session() as g:
        g.run(
            "MATCH (c:Company {company_id: $firm_id}) "
            "MATCH (p:Person {person_id: $person_id}) "
            "MERGE (c)-[r:AFFILIATED_WITH]->(p) "
            "SET r.role = $role",
            firm_id=firm_id,
            person_id=person_id,
            role=role,
        )


def _merge_involved_in(
    person_id: str, event_id: str, role: str, confidence: float
) -> None:
    with get_neo4j_session() as g:
        g.run(
            "MATCH (p:Person {person_id: $person_id}) "
            "MATCH (e:Event {event_id: $event_id}) "
            "MERGE (p)-[r:INVOLVED_IN]->(e) "
            "SET r.role_in_event = $role, r.confidence = $confidence",
            person_id=person_id,
            event_id=event_id,
            role=role,
            confidence=confidence,
        )


def _merge_connection(
    label_a: str, id_prop_a: str, id_a: str,
    label_b: str, id_prop_b: str, id_b: str,
    *,
    event_id: str,
    connection_type: str,
    intensity: float,
    description: str,
    source_url: str,
    source_title: str,
    occurred_at: str | None,
) -> None:
    cypher = (
        f"MATCH (a:{label_a} {{{id_prop_a}: $entity_1_id}}) "
        f"MATCH (b:{label_b} {{{id_prop_b}: $entity_2_id}}) "
        "MERGE (a)-[r:CONNECTION {source_event_id: $event_id}]->(b) "
        "SET r.type = $connection_type, "
        "    r.intensity = $intensity, "
        "    r.llm_description = $description, "
        "    r.source_url = $source_url, "
        "    r.source_title = $source_title, "
        "    r.event_occurred_at = $occurred_at, "
        "    r.scored_at = datetime()"
    )
    with get_neo4j_session() as g:
        g.run(
            cypher,
            entity_1_id=id_a,
            entity_2_id=id_b,
            event_id=event_id,
            connection_type=connection_type,
            intensity=intensity,
            description=description,
            source_url=source_url,
            source_title=source_title,
            occurred_at=occurred_at,
        )


def _label_and_id(entity_type: str) -> tuple[str, str]:
    et = entity_type.lower()
    if et == "person":
        return "Person", "person_id"
    if et == "event":
        return "Event", "event_id"
    return "Company", "company_id"


# ── Name → ID resolution ────────────────────────────────────────────────

def _build_firm_name_index(pg_session: Session) -> dict[str, int]:
    """Map lowercased firm names / aliases to Postgres firm IDs."""
    index: dict[str, int] = {}
    for firm in pg_session.scalars(select(Firm)).all():
        index[firm.full_name.lower()] = firm.id
    for alias in pg_session.scalars(select(FirmAlias)).all():
        index[alias.alias.lower()] = alias.firm_id
    return index


def _build_person_name_index(pg_session: Session, firm_id: int) -> dict[str, int]:
    """Map lowercased person names to Postgres person IDs (scoped to firm)."""
    index: dict[str, int] = {}
    persons = pg_session.scalars(select(Person).where(Person.firm_id == firm_id)).all()
    for p in persons:
        index[p.name.lower()] = p.id
    # Also include all persons linked to this firm's events
    event_ids = [
        e.unique_id for e in
        pg_session.scalars(select(Event).where(Event.firm_id == firm_id)).all()
    ]
    if event_ids:
        pe_links = pg_session.scalars(
            select(PersonEvent).where(PersonEvent.event_id.in_(event_ids))
        ).all()
        for link in pe_links:
            person = pg_session.get(Person, link.person_id)
            if person:
                index[person.name.lower()] = person.id
    return index


def _resolve_entity_id(
    entity_type: str,
    entity_id: str,
    entity_name: str | None,
    firm_index: dict[str, int],
    person_index: dict[str, int],
) -> tuple[str, str, str] | None:
    """Resolve a connection_entity ID to (label, id_prop, resolved_id).

    Returns None if the entity can't be matched to an existing Neo4j node.
    """
    et = entity_type.lower()

    # Already a numeric ID?
    try:
        int(entity_id)
        label, id_prop = _label_and_id(et)
        return label, id_prop, entity_id
    except (ValueError, TypeError):
        pass

    # Try name-based lookup
    name_key = (entity_name or entity_id or "").lower().strip()
    if not name_key:
        return None

    if et in ("company", "firm", "organization"):
        pg_id = firm_index.get(name_key)
        if pg_id is not None:
            return "Company", "company_id", str(pg_id)
    elif et == "person":
        pg_id = person_index.get(name_key)
        if pg_id is not None:
            return "Person", "person_id", str(pg_id)

    # Fallback: try both indexes
    pg_id = firm_index.get(name_key)
    if pg_id is not None:
        return "Company", "company_id", str(pg_id)
    pg_id = person_index.get(name_key)
    if pg_id is not None:
        return "Person", "person_id", str(pg_id)

    return None
