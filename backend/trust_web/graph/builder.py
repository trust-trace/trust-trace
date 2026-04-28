"""Phase 1 — Graph construction.

Reads Postgres to gather all entities around a firm, creates standalone
Neo4j nodes, then uses LLM to discover and create edges between them.

Tarkov writes raw data to Postgres (firms, events, persons, connection_entity
hints) but does NOT create any Neo4j edges.  All edge creation is TrustWeb's
responsibility, driven by LLM analysis of the source evidence.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from tarkov.database.models import (
    ConnectionEntity,
    Event,
    Firm,
    Person,
    PersonEvent,
    Source,
)
from tarkov.database.session import get_neo4j_session, init_neo4j

from trust_web.config import TrustWebConfig
from trust_web.graph import queries
from trust_web.schemas import EntityForDiscovery, GraphBuildResult, LLMEdge
from trust_web.scoring.intensity import build_fallback_edges, discover_edges

logger = logging.getLogger(__name__)


def _ensure_neo4j(config: TrustWebConfig) -> None:
    try:
        from tarkov.database.session import get_neo4j_driver
        get_neo4j_driver()
    except RuntimeError:
        init_neo4j(config.neo4j_uri, config.neo4j_user, config.neo4j_password)


async def build_graph_for_firm(
    firm_id: int,
    pg_session: Session,
    config: TrustWebConfig,
    *,
    force_rescore: bool = False,
) -> GraphBuildResult:
    """Build the Neo4j graph around a firm.

    1. Read Postgres for all related entities (firms, events, persons)
    2. Create standalone Neo4j nodes for each entity
    3. Collect source evidence texts
    4. Ask LLM to discover edges (or fall back to heuristics)
    5. Write LLM-determined edges to Neo4j
    """
    _ensure_neo4j(config)
    result = GraphBuildResult()

    firm = pg_session.get(Firm, firm_id)
    if firm is None:
        result.errors.append(f"Firm {firm_id} not found")
        return result

    # ── Step 1: Gather all related entities from Postgres ──────────────

    entities: list[EntityForDiscovery] = []
    evidence_texts: list[str] = []
    events_by_firm: dict[str, list[str]] = {}  # firm_id_str → [event_id, ...]
    persons_by_firm: dict[str, list[str]] = {}  # firm_id_str → [person_id, ...]
    connection_hints: list[dict] = []

    # Root firm
    entities.append(EntityForDiscovery(
        entity_id=str(firm_id),
        entity_type="Company",
        name=firm.full_name,
        context=f"country={firm.country}",
    ))

    # All events for this firm
    events = pg_session.scalars(
        select(Event).where(Event.firm_id == firm_id)
    ).all()

    firm_event_ids: list[str] = []
    for event in events:
        entities.append(EntityForDiscovery(
            entity_id=event.unique_id,
            entity_type="Event",
            name=event.title,
            context=f"type={event.event_type}, category={event.event_category}, risk_level={event.risk_level}",
            occurred_at=event.occurred_at,
        ))
        firm_event_ids.append(event.unique_id)

        if event.source_text_quote:
            evidence_texts.append(
                f"[Event: {event.title}] {event.source_text_quote}"
            )

        # Also grab source article text as evidence
        sources = pg_session.scalars(
            select(Source).where(Source.event_id == event.unique_id)
        ).all()
        for src in sources:
            if src.content:
                evidence_texts.append(
                    f"[Source: {src.title or src.url}] {src.content}"
                )

    events_by_firm[str(firm_id)] = firm_event_ids

    # Persons linked to this firm's events
    firm_person_ids: list[str] = []
    for event in events:
        if event.event_category == "people":
            pe_rows = pg_session.scalars(
                select(PersonEvent).where(PersonEvent.event_id == event.unique_id)
            ).all()
            for pe in pe_rows:
                person = pg_session.get(Person, pe.person_id)
                if person is None:
                    continue
                pid = str(person.id)
                if not any(e.entity_id == pid for e in entities):
                    entities.append(EntityForDiscovery(
                        entity_id=pid,
                        entity_type="Person",
                        name=person.name,
                        context=f"role={person.role or 'unknown'}"
                            + (f", firm_id={person.firm_id}" if person.firm_id else ""),
                    ))
                firm_person_ids.append(pid)

    # Also add persons directly affiliated with the firm
    direct_persons = pg_session.scalars(
        select(Person).where(Person.firm_id == firm_id)
    ).all()
    for person in direct_persons:
        pid = str(person.id)
        if not any(e.entity_id == pid for e in entities):
            entities.append(EntityForDiscovery(
                entity_id=pid,
                entity_type="Person",
                name=person.name,
                context=f"role={person.role or 'unknown'}, firm_id={person.firm_id}",
            ))
        if pid not in firm_person_ids:
            firm_person_ids.append(pid)

    persons_by_firm[str(firm_id)] = firm_person_ids

    # Neighbor firms from connection_entity hints
    neighbor_firm_ids = _find_neighbor_firm_ids(events, firm_id, pg_session)
    for nf_id in neighbor_firm_ids:
        nf = pg_session.get(Firm, nf_id)
        if nf is None:
            continue
        nf_id_str = str(nf_id)
        if not any(e.entity_id == nf_id_str for e in entities):
            entities.append(EntityForDiscovery(
                entity_id=nf_id_str,
                entity_type="Company",
                name=nf.full_name,
                context=f"country={nf.country}",
            ))

        # Load neighbor firm's events and persons too
        nf_events = pg_session.scalars(
            select(Event).where(Event.firm_id == nf_id)
        ).all()
        nf_event_ids: list[str] = []
        nf_person_ids: list[str] = []
        for evt in nf_events:
            if not any(e.entity_id == evt.unique_id for e in entities):
                entities.append(EntityForDiscovery(
                    entity_id=evt.unique_id,
                    entity_type="Event",
                    name=evt.title,
                    context=f"type={evt.event_type}, category={evt.event_category}, risk_level={evt.risk_level}",
                    occurred_at=evt.occurred_at,
                ))
            nf_event_ids.append(evt.unique_id)

            if evt.source_text_quote:
                evidence_texts.append(
                    f"[Event: {evt.title}] {evt.source_text_quote}"
                )

            if evt.event_category == "people":
                pe_rows = pg_session.scalars(
                    select(PersonEvent).where(PersonEvent.event_id == evt.unique_id)
                ).all()
                for pe in pe_rows:
                    person = pg_session.get(Person, pe.person_id)
                    if person is None:
                        continue
                    pid = str(person.id)
                    if not any(e.entity_id == pid for e in entities):
                        entities.append(EntityForDiscovery(
                            entity_id=pid,
                            entity_type="Person",
                            name=person.name,
                            context=f"role={person.role or 'unknown'}",
                        ))
                    nf_person_ids.append(pid)

        events_by_firm[nf_id_str] = nf_event_ids
        persons_by_firm[nf_id_str] = nf_person_ids

    # Collect connection_entity rows as hints for the fallback
    for event in events:
        if event.event_category == "connection":
            ce_rows = pg_session.scalars(
                select(ConnectionEntity).where(
                    ConnectionEntity.connection_event_id == event.unique_id
                )
            ).all()
            for ce in ce_rows:
                connection_hints.append({
                    "entity_1_id": ce.entity_1_id,
                    "entity_2_id": ce.entity_2_id,
                    "entity_1_type": ce.entity_1_type,
                    "entity_2_type": ce.entity_2_type,
                    "connection_type": ce.connection_type,
                    "relationship_description": ce.relationship_description or "",
                    "confidence": ce.confidence or 0.5,
                })

    # ── Step 2: Create standalone Neo4j nodes ──────────────────────────

    for entity in entities:
        _merge_node(entity)
        result.nodes_created += 1

    logger.info(
        "Created %d standalone nodes for firm %d (%d companies, %d persons, %d events)",
        len(entities), firm_id,
        sum(1 for e in entities if e.entity_type == "Company"),
        sum(1 for e in entities if e.entity_type == "Person"),
        sum(1 for e in entities if e.entity_type == "Event"),
    )

    # ── Step 3: LLM edge discovery ────────────────────────────────────

    llm_edges = await discover_edges(
        firm_id, firm.full_name, entities, evidence_texts, config,
    )

    if llm_edges:
        result.llm_edges_discovered = len(llm_edges)
        logger.info("LLM discovered %d edges for firm %d", len(llm_edges), firm_id)
    else:
        # Fall back to heuristic edges from Postgres hints
        llm_edges = build_fallback_edges(
            firm_id, entities, events_by_firm, persons_by_firm, connection_hints,
        )
        result.fallback_edges_created = len(llm_edges)
        logger.warning(
            "⚠️  NO LLM — created %d FALLBACK edges for firm %d. "
            "These are heuristic edges from Postgres data, NOT LLM-analyzed. "
            "Scores will be less accurate. Set TRUSTWEB_LLM_API_KEY for real analysis.",
            len(llm_edges), firm_id,
        )

    # ── Step 4: Write edges to Neo4j ──────────────────────────────────

    entity_map = {e.entity_id: e for e in entities}
    for edge in llm_edges:
        _write_edge(edge, entity_map, pg_session)
        result.edges_created += 1

    return result


# ── Neo4j helpers ──────────────────────────────────────────────────────────

def _merge_node(entity: EntityForDiscovery) -> None:
    """Create or update a standalone node in Neo4j."""
    with get_neo4j_session() as g:
        if entity.entity_type == "Company":
            g.run(queries.MERGE_COMPANY_NODE,
                  company_id=entity.entity_id, name=entity.name)
        elif entity.entity_type == "Person":
            g.run(queries.MERGE_PERSON_NODE,
                  person_id=entity.entity_id, name=entity.name)
        elif entity.entity_type == "Event":
            parts = {}
            for part in entity.context.split(", "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parts[k] = v
            occurred_str = entity.occurred_at.isoformat() if entity.occurred_at else None
            g.run(queries.MERGE_EVENT_NODE,
                  event_id=entity.entity_id,
                  title=entity.name,
                  risk_level=int(parts.get("risk_level", 0)),
                  event_type=parts.get("type", "unknown"),
                  occurred_at=occurred_str)


def _write_edge(
    edge: LLMEdge,
    entity_map: dict[str, EntityForDiscovery],
    pg_session: Session,
) -> None:
    """Write a single LLM-discovered edge to Neo4j."""
    src = entity_map.get(edge.source_entity_id)
    tgt = entity_map.get(edge.target_entity_id)
    if not src or not tgt:
        return

    source_url, source_title = None, None
    if tgt.entity_type == "Event":
        source_url, source_title = _get_source_article(tgt.entity_id, pg_session)
    elif src.entity_type == "Event":
        source_url, source_title = _get_source_article(src.entity_id, pg_session)

    # Resolve the event's occurred_at for the edge
    event_occurred_at = None
    for ent in (tgt, src):
        if ent.entity_type == "Event" and ent.occurred_at:
            event_occurred_at = ent.occurred_at.isoformat()
            break

    with get_neo4j_session() as g:
        if edge.relationship_type == "CONNECTION":
            label_a, id_prop_a = _label_and_id(src.entity_type)
            label_b, id_prop_b = _label_and_id(tgt.entity_type)
            cypher = queries.MERGE_CONNECTION_EDGE.format(
                label_a=label_a, id_prop_a=id_prop_a,
                label_b=label_b, id_prop_b=id_prop_b,
            )
            g.run(cypher,
                  entity_1_id=edge.source_entity_id,
                  entity_2_id=edge.target_entity_id,
                  event_id=edge.source_entity_id,
                  connection_type=edge.connection_subtype or "business_relationship",
                  intensity=edge.intensity,
                  llm_description=edge.description,
                  source_url=source_url or "",
                  source_title=source_title or "",
                  event_occurred_at=event_occurred_at)
        elif edge.relationship_type == "ABOUT":
            g.run(queries.MERGE_ABOUT_EDGE,
                  firm_id=edge.source_entity_id,
                  event_id=edge.target_entity_id)
        elif edge.relationship_type == "INVOLVED_IN":
            g.run(queries.MERGE_INVOLVED_IN_EDGE,
                  person_id=edge.source_entity_id,
                  event_id=edge.target_entity_id,
                  role="", confidence=edge.intensity)
        elif edge.relationship_type == "AFFILIATED_WITH":
            g.run(queries.MERGE_AFFILIATED_WITH_EDGE,
                  firm_id=edge.source_entity_id,
                  person_id=edge.target_entity_id,
                  role="")


def _label_and_id(entity_type: str) -> tuple[str, str]:
    if entity_type == "Person":
        return "Person", "person_id"
    if entity_type == "Event":
        return "Event", "event_id"
    return "Company", "company_id"


def _get_source_article(event_id: str, pg_session: Session) -> tuple[str | None, str | None]:
    row = pg_session.execute(
        select(Source.url, Source.title).where(
            and_(
                Source.event_id == event_id,
                Source.source_category == "article",
            )
        ).limit(1)
    ).first()
    if row:
        return row.url, row.title
    return None, None


def _find_neighbor_firm_ids(
    events: list,
    firm_id: int,
    pg_session: Session,
) -> set[int]:
    """Find firm IDs of neighboring companies from connection_entity hints."""
    neighbor_ids: set[int] = set()
    for event in events:
        if event.event_category != "connection":
            continue
        ce_rows = pg_session.scalars(
            select(ConnectionEntity).where(
                ConnectionEntity.connection_event_id == event.unique_id
            )
        ).all()
        for ce in ce_rows:
            for etype, eid in [(ce.entity_1_type, ce.entity_1_id),
                               (ce.entity_2_type, ce.entity_2_id)]:
                if etype == "company":
                    try:
                        nid = int(eid)
                        if nid != firm_id:
                            neighbor_ids.add(nid)
                    except (ValueError, TypeError):
                        pass
    return neighbor_ids
