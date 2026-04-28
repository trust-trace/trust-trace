"""TrustWeb — Graph-based AML risk scoring (Module C).

Public API
----------
    from trust_web import score_firm

    result = await score_firm(firm_id=123)

Everything else (graph construction, subgraph extraction, propagation,
explanation generation) happens internally and results are persisted to
Postgres as side effects.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["score_firm"]

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from tarkov.database.models import Firm
from timeline.buckets import compute_timeline_buckets
from trust_web.config import TrustWebConfig
from trust_web.graph.builder import build_graph_for_firm
from trust_web.graph.traversal import extract_subgraph, filter_subgraph_by_cutoff, _enrich_risk_levels
from trust_web.schemas import (
    TrustWebResult,
    TrustWebTimelineEntry,
    TrustWebTimelineResult,
)
from trust_web.scoring.aggregator import compute_trustweb_score, _build_summary

logger = logging.getLogger(__name__)


async def score_firm(
    firm_id: int,
    *,
    pg_session: Session | None = None,
    config: TrustWebConfig | None = None,
    force_rescore: bool = False,
) -> TrustWebTimelineResult:
    """Score a firm's AML risk via graph-based analysis with timeline.

    Returns a ``TrustWebTimelineResult`` containing 8 timeline entries
    and one explanation describing the trajectory.

    Side effects: persists the full result to ``trustweb_score_timeline``
    and ``trustweb_run`` Postgres tables, plus the legacy ``trustweb_score`` table.
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
) -> TrustWebTimelineResult:
    # Resolve founding date for bucketing
    firm = pg_session.get(Firm, firm_id)
    if firm is None:
        raise ValueError(f"Firm {firm_id} not found")
    founding = firm.founded_at or firm.created_at or datetime.utcnow()
    buckets = compute_timeline_buckets(founding)

    # Phase 1 — Graph construction (once, from all data)
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

    # Phase 2 — Extract full subgraph once
    full_subgraph = extract_subgraph(firm_id, pg_session, config)

    # Phase 3 — Score per bucket with filtered subgraph
    run_id = str(uuid.uuid4())
    timeline_entries: list[TrustWebTimelineEntry] = []

    for bucket in buckets:
        filtered = filter_subgraph_by_cutoff(full_subgraph, bucket.end)
        _enrich_risk_levels(filtered, pg_session, cutoff=bucket.end)

        result_i = await compute_trustweb_score(
            firm_id, filtered, pg_session, config, skip_explanation=True,
        )

        summary = _build_summary(filtered)
        entry = TrustWebTimelineEntry(
            bucket_index=bucket.index,
            bucket_start=bucket.start,
            bucket_end=bucket.end,
            score=result_i.score,
            node_count=summary.total_nodes,
            edge_count=summary.total_edges,
            max_depth_used=result_i.max_depth_used,
        )
        timeline_entries.append(entry)

    # Phase 4 — One explanation for the full trajectory
    explanation = await _generate_trajectory_explanation(
        firm_id, timeline_entries, full_subgraph, pg_session, config,
    )

    timeline_result = TrustWebTimelineResult(
        firm_id=firm_id,
        entries=timeline_entries,
        explanation=explanation,
        computed_at=datetime.now(timezone.utc),
    )

    # Persist timeline + legacy score
    _persist_timeline(firm_id, run_id, timeline_result, pg_session)
    _persist_legacy_score(firm_id, timeline_result, build_result, pg_session)

    return timeline_result


async def _generate_trajectory_explanation(
    firm_id: int,
    entries: list[TrustWebTimelineEntry],
    subgraph,
    pg_session: Session,
    config: TrustWebConfig,
) -> str:
    """Generate one LLM explanation describing the score trajectory."""
    from trust_web.llm.client import chat_completion

    firm = pg_session.get(Firm, firm_id)
    firm_name = firm.full_name if firm else f"Firm-{firm_id}"

    scores_str = ", ".join(
        f"T{e.bucket_index}({e.bucket_start.strftime('%Y-%m')}): {e.score:.3f}"
        for e in entries
    )

    first_score = entries[0].score
    last_score = entries[-1].score
    trend = "stable"
    if last_score > first_score + 0.1:
        trend = "increasing risk"
    elif last_score < first_score - 0.1:
        trend = "decreasing risk"

    prompt = (
        f"Company: {firm_name} (ID: {firm_id})\n"
        f"TrustWeb timeline scores: {scores_str}\n"
        f"Overall trend: {trend}\n"
        f"Latest network: {entries[-1].node_count} nodes, {entries[-1].edge_count} edges\n\n"
        f"Write a 2-3 paragraph compliance-ready explanation of how this firm's "
        f"network risk evolved over time. Be specific about what changed and when."
    )

    system = (
        "You are an AML compliance analyst. Given a timeline of graph-based risk "
        "scores for a company's network, write a clear explanation of how the risk "
        "evolved. Be specific: name time periods, score changes, and what likely "
        "drove them. Write 2-3 concise paragraphs suitable for a compliance report."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    explanation = await chat_completion(
        messages, config, model=config.llm_explanation_model, max_tokens=1200,
    )

    if not explanation:
        explanation = (
            f"TrustWeb timeline analysis for {firm_name}: risk score evolved from "
            f"{first_score:.3f} to {last_score:.3f} over {len(entries)} periods. "
            f"Trend: {trend}."
        )

    return explanation


def _persist_timeline(
    firm_id: int,
    run_id: str,
    result: TrustWebTimelineResult,
    pg_session: Session,
) -> None:
    """Write timeline rows and run-level explanation to Postgres."""
    try:
        # Write run-level row
        pg_session.execute(
            text(
                "INSERT INTO trustweb_run (run_id, firm_id, explanation, computed_at) "
                "VALUES (:run_id, :firm_id, :explanation, :computed_at)"
            ),
            {
                "run_id": run_id,
                "firm_id": firm_id,
                "explanation": result.explanation,
                "computed_at": result.computed_at,
            },
        )

        # Write per-bucket rows
        for entry in result.entries:
            pg_session.execute(
                text(
                    "INSERT INTO trustweb_score_timeline "
                    "(firm_id, run_id, bucket_index, bucket_start, bucket_end, "
                    "score, node_count, edge_count, max_depth_used, computed_at) "
                    "VALUES (:firm_id, :run_id, :bucket_index, :bucket_start, :bucket_end, "
                    ":score, :node_count, :edge_count, :max_depth_used, :computed_at)"
                ),
                {
                    "firm_id": firm_id,
                    "run_id": run_id,
                    "bucket_index": entry.bucket_index,
                    "bucket_start": entry.bucket_start,
                    "bucket_end": entry.bucket_end,
                    "score": entry.score,
                    "node_count": entry.node_count,
                    "edge_count": entry.edge_count,
                    "max_depth_used": entry.max_depth_used,
                    "computed_at": result.computed_at,
                },
            )
        pg_session.commit()
    except Exception:
        logger.exception("Failed to persist TrustWeb timeline for firm %d", firm_id)
        pg_session.rollback()


def _persist_legacy_score(
    firm_id: int,
    timeline_result: TrustWebTimelineResult,
    build_result,
    pg_session: Session,
) -> None:
    """Also write to the legacy ``trustweb_score`` table for backward compatibility."""
    latest = timeline_result.entries[-1]
    try:
        pg_session.execute(
            text(
                "INSERT INTO trustweb_score "
                "(firm_id, score, explanation, node_count, edge_count, max_depth_used, computed_at) "
                "VALUES (:firm_id, :score, :explanation, :node_count, :edge_count, :max_depth_used, :computed_at)"
            ),
            {
                "firm_id": firm_id,
                "score": latest.score,
                "explanation": timeline_result.explanation,
                "node_count": latest.node_count,
                "edge_count": latest.edge_count,
                "max_depth_used": latest.max_depth_used,
                "computed_at": timeline_result.computed_at,
            },
        )
        pg_session.commit()
    except Exception:
        logger.exception("Failed to persist legacy TrustWeb score for firm %d", firm_id)
        pg_session.rollback()
