"""TrustWeb — Graph-based AML risk scoring (Module C).

Public API
----------
    from trust_web import score_firm

    score = await score_firm(firm_id=123)

Everything else (graph construction, subgraph extraction, propagation,
explanation generation) happens internally and results are persisted to
Postgres as side effects.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["score_firm"]

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from trust_web.config import TrustWebConfig
from trust_web.graph.builder import build_graph_for_firm
from trust_web.graph.traversal import extract_subgraph
from trust_web.schemas import TrustWebResult
from trust_web.scoring.aggregator import compute_trustweb_score

logger = logging.getLogger(__name__)


async def score_firm(
    firm_id: int,
    *,
    pg_session: Session | None = None,
    config: TrustWebConfig | None = None,
    force_rescore: bool = False,
) -> float:
    """Score a firm's AML risk via graph-based analysis.

    Returns a 0.0–1.0 risk score.

    Side effects: persists the full result (explanation, subgraph summary,
    etc.) to the ``trustweb_score`` Postgres table.

    Parameters ``pg_session`` and ``config`` are optional overrides —
    when omitted, a session is created from the already-initialised engine
    and config is loaded from env vars.
    """
    if config is None:
        config = TrustWebConfig.from_env()

    owns_session = pg_session is None
    if owns_session:
        from tarkov.database.session import SessionLocal
        pg_session = SessionLocal()

    try:
        return await _run_scoring(firm_id, pg_session, config, force_rescore)
    finally:
        if owns_session:
            pg_session.close()


async def _run_scoring(
    firm_id: int,
    pg_session: Session,
    config: TrustWebConfig,
    force_rescore: bool,
) -> float:
    # Phase 1 — Graph construction
    build_result = await build_graph_for_firm(
        firm_id, pg_session, config, force_rescore=force_rescore,
    )
    logger.info(
        "Graph build complete for firm %d: %d nodes, %d edges (%d LLM-discovered, %d fallback)",
        firm_id,
        build_result.nodes_created,
        build_result.edges_created,
        build_result.llm_edges_discovered,
        build_result.fallback_edges_created,
    )

    # Phase 2 — Subgraph extraction + risk propagation + explanation
    subgraph = extract_subgraph(firm_id, pg_session, config)
    result = await compute_trustweb_score(firm_id, subgraph, pg_session, config)
    result.connections_scored = build_result.edges_created

    # Persist to Postgres
    _persist_score(firm_id, result, pg_session)

    return result.score


def _persist_score(firm_id: int, result: TrustWebResult, pg_session: Session) -> None:
    """Write the TrustWeb score to the trustweb_score table."""
    try:
        pg_session.execute(
            text(
                "INSERT INTO trustweb_score "
                "(firm_id, score, explanation, node_count, edge_count, max_depth_used, computed_at) "
                "VALUES (:firm_id, :score, :explanation, :node_count, :edge_count, :max_depth_used, :computed_at)"
            ),
            {
                "firm_id": firm_id,
                "score": result.score,
                "explanation": result.explanation,
                "node_count": result.subgraph_summary.total_nodes,
                "edge_count": result.subgraph_summary.total_edges,
                "max_depth_used": result.max_depth_used,
                "computed_at": result.computed_at,
            },
        )
        pg_session.commit()
    except Exception:
        logger.exception("Failed to persist TrustWeb score for firm %d", firm_id)
        pg_session.rollback()
