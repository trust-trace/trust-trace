"""Phase 2, steps 1-2 — Subgraph extraction from Neo4j."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tarkov.database.models import Event as EventModel, Firm
from tarkov.database.session import get_neo4j_session

from trust_web.config import TrustWebConfig
from trust_web.graph.queries import EXTRACT_SUBGRAPH
from trust_web.schemas import SubgraphData, SubgraphEdge, SubgraphNode

logger = logging.getLogger(__name__)


def extract_subgraph(
    firm_id: int,
    pg_session: Session,
    config: TrustWebConfig,
) -> SubgraphData:
    """Extract the ego-network subgraph around a firm from Neo4j,
    then enrich risk levels from Postgres."""
    cypher = EXTRACT_SUBGRAPH.format(max_depth=config.max_depth)

    nodes_by_id: dict[str, SubgraphNode] = {}
    edges: list[SubgraphEdge] = []
    max_depth_reached = 0

    # Add root node
    firm = pg_session.get(Firm, firm_id)
    root_name = firm.full_name if firm else f"Firm-{firm_id}"
    root_id = str(firm_id)
    nodes_by_id[root_id] = SubgraphNode(
        node_id=root_id,
        node_type="Company",
        name=root_name,
        depth=0,
        risk_level=None,
    )

    try:
        with get_neo4j_session() as g:
            result = g.run(cypher, firm_id=str(firm_id))
            for record in result:
                neighbor = record["neighbor"]
                labels = record["neighbor_labels"]
                edge_info = record["edge_info"]
                depth = record["depth"]

                max_depth_reached = max(max_depth_reached, depth)

                node_type = _primary_label(labels)
                node_id = _extract_node_id(neighbor, node_type)
                node_name = _extract_node_name(neighbor, node_type)

                if node_id and node_id not in nodes_by_id:
                    node_occurred_at = _parse_datetime(neighbor.get("occurred_at")) if node_type == "Event" else None
                    nodes_by_id[node_id] = SubgraphNode(
                        node_id=node_id,
                        node_type=node_type,
                        name=node_name,
                        depth=depth,
                        risk_level=None,
                        occurred_at=node_occurred_at,
                    )

                for ei in edge_info:
                    src_id = _resolve_edge_endpoint(ei, "source")
                    tgt_id = _resolve_edge_endpoint(ei, "target")
                    if src_id and tgt_id:
                        edges.append(SubgraphEdge(
                            source_id=src_id,
                            target_id=tgt_id,
                            relationship_type=ei.get("type", "CONNECTION"),
                            intensity=ei.get("intensity"),
                            connection_subtype=ei.get("conn_type"),
                            llm_description=ei.get("llm_description"),
                            source_url=ei.get("source_url"),
                            source_title=ei.get("source_title"),
                            event_occurred_at=_parse_datetime(ei.get("event_occurred_at")),
                        ))
    except Exception:
        logger.exception("Failed to extract subgraph for firm %d", firm_id)

    # Deduplicate edges
    seen_edges: set[tuple[str, str, str]] = set()
    unique_edges: list[SubgraphEdge] = []
    for e in edges:
        key = (e.source_id, e.target_id, e.relationship_type)
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    subgraph = SubgraphData(
        root_firm_id=firm_id,
        nodes=list(nodes_by_id.values()),
        edges=unique_edges,
        max_depth_reached=max_depth_reached,
    )

    _enrich_risk_levels(subgraph, pg_session)
    return subgraph


def _enrich_risk_levels(
    subgraph: SubgraphData,
    pg_session: Session,
    cutoff: datetime | None = None,
) -> None:
    """Fill in risk_level for Company and Event nodes from Postgres.

    When *cutoff* is provided, reputation scores are filtered to those
    computed on or before the cutoff date (``WHERE calculated_at <= :cutoff``).
    """
    for node in subgraph.nodes:
        if node.node_type == "Company":
            try:
                from tarkov.database.models import Firm
                row = pg_session.execute(
                    select(Firm.id).where(Firm.id == int(node.node_id))
                ).first()
                if row:
                    from sqlalchemy import text
                    if cutoff is not None:
                        rep = pg_session.execute(
                            text(
                                "SELECT score FROM reputation_score "
                                "WHERE firm_id = :fid AND calculated_at <= :cutoff "
                                "ORDER BY calculated_at DESC LIMIT 1"
                            ),
                            {"fid": int(node.node_id), "cutoff": cutoff},
                        ).scalar()
                    else:
                        rep = pg_session.execute(
                            text(
                                "SELECT score FROM reputation_score "
                                "WHERE firm_id = :fid ORDER BY calculated_at DESC LIMIT 1"
                            ),
                            {"fid": int(node.node_id)},
                        ).scalar()
                    if rep is not None:
                        node.risk_level = float(rep)
            except (ValueError, TypeError):
                pass

        elif node.node_type == "Event":
            try:
                evt = pg_session.get(EventModel, node.node_id)
                if evt and evt.risk_level:
                    node.risk_level = evt.risk_level / 10.0
            except Exception:
                pass


def _primary_label(labels: list[str]) -> str:
    for preferred in ("Company", "Person", "Event"):
        if preferred in labels:
            return preferred
    return labels[0] if labels else "Unknown"


def _extract_node_id(node: dict, node_type: str) -> str | None:
    if node_type == "Company":
        return node.get("company_id")
    if node_type == "Person":
        return node.get("person_id")
    if node_type == "Event":
        return node.get("event_id")
    return node.get("company_id") or node.get("person_id") or node.get("event_id")


def _extract_node_name(node: dict, node_type: str) -> str:
    return node.get("name") or node.get("title") or node.get("full_name") or "Unknown"


def _resolve_edge_endpoint(ei: dict, prefix: str) -> str | None:
    """Resolve edge endpoint ID from edge_info dict.

    The subgraph query returns source/target IDs for each node type;
    exactly one should be non-null.
    """
    if prefix == "source":
        return (
            ei.get("source_id")
            or ei.get("source_person_id")
            or ei.get("source_event_id_prop")
        )
    return (
        ei.get("target_id")
        or ei.get("target_person_id")
        or ei.get("target_event_id_prop")
    )


def _parse_datetime(value: object) -> datetime | None:
    """Best-effort parse of a datetime value from Neo4j."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # neo4j python driver may return neo4j.time.DateTime
        if hasattr(value, "to_native"):
            return value.to_native()  # type: ignore[union-attr]
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def filter_subgraph_by_cutoff(
    full_subgraph: SubgraphData,
    cutoff: datetime,
) -> SubgraphData:
    """Return a copy with only entities active by *cutoff*.

    - Company nodes are always kept (they exist from founding).
    - Event nodes are kept only if ``occurred_at <= cutoff``.
    - Person nodes are kept if any linked edge survives the cutoff.
    - Edges are kept if both endpoints survive AND
      ``event_occurred_at <= cutoff`` (when the date is available).
    """
    # 1. Determine which Company and Event nodes survive
    surviving_node_ids: set[str] = set()
    for node in full_subgraph.nodes:
        if node.node_type == "Company":
            surviving_node_ids.add(node.node_id)
        elif node.node_type == "Event":
            if node.occurred_at is None or node.occurred_at <= cutoff:
                surviving_node_ids.add(node.node_id)

    # 2. Filter edges — keep if event date is in range and at least one
    #    endpoint is a surviving Company/Event (Person resolved in step 3)
    person_node_ids = {n.node_id for n in full_subgraph.nodes if n.node_type == "Person"}
    candidate_edges: list[SubgraphEdge] = []
    person_ids_with_edges: set[str] = set()

    for edge in full_subgraph.edges:
        if edge.event_occurred_at is not None and edge.event_occurred_at > cutoff:
            continue
        src_ok = edge.source_id in surviving_node_ids or edge.source_id in person_node_ids
        tgt_ok = edge.target_id in surviving_node_ids or edge.target_id in person_node_ids
        if not (src_ok and tgt_ok):
            continue
        # At least one non-Person endpoint must survive
        src_survives = edge.source_id in surviving_node_ids
        tgt_survives = edge.target_id in surviving_node_ids
        if not (src_survives or tgt_survives):
            continue
        candidate_edges.append(edge)
        if edge.source_id in person_node_ids:
            person_ids_with_edges.add(edge.source_id)
        if edge.target_id in person_node_ids:
            person_ids_with_edges.add(edge.target_id)

    # 3. Person nodes survive if they have at least one surviving edge
    surviving_node_ids.update(person_ids_with_edges)

    # Final edge filter: both endpoints must be in the surviving set
    final_edges = [
        e for e in candidate_edges
        if e.source_id in surviving_node_ids and e.target_id in surviving_node_ids
    ]

    surviving_nodes = [n for n in full_subgraph.nodes if n.node_id in surviving_node_ids]

    return SubgraphData(
        root_firm_id=full_subgraph.root_firm_id,
        nodes=surviving_nodes,
        edges=final_edges,
        max_depth_reached=full_subgraph.max_depth_reached,
    )
