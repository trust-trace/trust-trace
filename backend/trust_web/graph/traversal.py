"""Phase 2, steps 1-2 — Subgraph extraction from Neo4j."""

from __future__ import annotations

import logging

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
                    nodes_by_id[node_id] = SubgraphNode(
                        node_id=node_id,
                        node_type=node_type,
                        name=node_name,
                        depth=depth,
                        risk_level=None,
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


def _enrich_risk_levels(subgraph: SubgraphData, pg_session: Session) -> None:
    """Fill in risk_level for Company and Event nodes from Postgres."""
    for node in subgraph.nodes:
        if node.node_type == "Company":
            try:
                from tarkov.database.models import Firm
                # Use latest reputation_score if available
                row = pg_session.execute(
                    select(Firm.id).where(Firm.id == int(node.node_id))
                ).first()
                if row:
                    from sqlalchemy import text
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
