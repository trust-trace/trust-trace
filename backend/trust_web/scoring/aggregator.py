"""Final score computation + LLM explanation generation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from tarkov.database.models import Firm

from trust_web.config import TrustWebConfig
from trust_web.llm.client import chat_completion
from trust_web.llm.prompts import EXPLANATION_SYSTEM, EXPLANATION_USER
from trust_web.schemas import (
    PropagationResult,
    SubgraphData,
    SubgraphSummary,
    TrustWebResult,
)
from trust_web.scoring.propagation import propagate_risk

logger = logging.getLogger(__name__)


async def compute_trustweb_score(
    firm_id: int,
    subgraph: SubgraphData,
    pg_session: Session,
    config: TrustWebConfig,
) -> TrustWebResult:
    """Run propagation, generate explanation, and return the final result."""
    # Handle isolated firm
    if len(subgraph.nodes) <= 1 and not subgraph.edges:
        return TrustWebResult(
            firm_id=firm_id,
            score=0.0,
            explanation="No network connections found for this entity.",
            subgraph_summary=_build_summary(subgraph),
            connections_scored=0,
            max_depth_used=0,
            computed_at=datetime.now(timezone.utc),
        )

    # Run propagation
    prop_result = propagate_risk(subgraph, config)

    root_key = str(firm_id)
    numeric_score = prop_result.risk_map.get(root_key, 0.0)
    numeric_score = max(0.0, min(1.0, numeric_score))

    summary = _build_summary(subgraph)

    # Generate LLM explanation
    explanation = await _generate_explanation(
        firm_id, numeric_score, subgraph, summary, prop_result, pg_session, config,
    )

    return TrustWebResult(
        firm_id=firm_id,
        score=numeric_score,
        explanation=explanation,
        subgraph_summary=summary,
        connections_scored=len([e for e in subgraph.edges if e.relationship_type == "CONNECTION"]),
        max_depth_used=subgraph.max_depth_reached,
        computed_at=datetime.now(timezone.utc),
    )


async def _generate_explanation(
    firm_id: int,
    score: float,
    subgraph: SubgraphData,
    summary: SubgraphSummary,
    prop_result: PropagationResult,
    pg_session: Session,
    config: TrustWebConfig,
) -> str:
    """Ask the LLM to produce a human-readable risk explanation."""
    firm = pg_session.get(Firm, firm_id)
    firm_name = firm.full_name if firm else f"Firm-{firm_id}"

    top_contributors = _format_top_contributors(subgraph, prop_result, limit=5)

    user_msg = EXPLANATION_USER.format(
        firm_name=firm_name,
        firm_id=firm_id,
        score=score,
        node_count=summary.total_nodes,
        company_count=summary.company_count,
        person_count=summary.person_count,
        event_count=summary.event_count,
        edge_count=summary.total_edges,
        max_depth=summary.max_depth,
        top_contributors=top_contributors,
    )

    messages = [
        {"role": "system", "content": EXPLANATION_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    explanation = await chat_completion(
        messages, config, model=config.llm_explanation_model, max_tokens=1200,
    )

    if not explanation:
        explanation = _fallback_explanation(firm_name, score, summary, top_contributors)

    return explanation


def _build_summary(subgraph: SubgraphData) -> SubgraphSummary:
    company_count = sum(1 for n in subgraph.nodes if n.node_type == "Company")
    person_count = sum(1 for n in subgraph.nodes if n.node_type == "Person")
    event_count = sum(1 for n in subgraph.nodes if n.node_type == "Event")
    return SubgraphSummary(
        total_nodes=len(subgraph.nodes),
        total_edges=len(subgraph.edges),
        company_count=company_count,
        person_count=person_count,
        event_count=event_count,
        max_depth=subgraph.max_depth_reached,
    )


def _format_top_contributors(
    subgraph: SubgraphData,
    prop_result: PropagationResult,
    limit: int = 5,
) -> str:
    """Format the highest-risk neighbors for the explanation prompt."""
    root_id = str(subgraph.root_firm_id)
    neighbors = [
        (nid, risk)
        for nid, risk in prop_result.risk_map.items()
        if nid != root_id and risk > 0.0
    ]
    neighbors.sort(key=lambda x: x[1], reverse=True)
    neighbors = neighbors[:limit]

    if not neighbors:
        return "- No significant risk contributors identified."

    node_map = {n.node_id: n for n in subgraph.nodes}
    lines = []
    for nid, risk in neighbors:
        node = node_map.get(nid)
        name = node.name if node else nid
        ntype = node.node_type if node else "Unknown"
        depth = node.depth if node else "?"
        lines.append(f"- {name} ({ntype}, depth {depth}): risk {risk:.3f}")

    return "\n".join(lines)


def _fallback_explanation(
    firm_name: str,
    score: float,
    summary: SubgraphSummary,
    top_contributors: str,
) -> str:
    """Deterministic explanation when LLM is unavailable."""
    level = "low" if score < 0.3 else ("moderate" if score < 0.6 else "high")
    return (
        f"TrustWeb analysis for {firm_name} yielded a {level} graph-based risk score "
        f"of {score:.3f}. The analysis examined {summary.total_nodes} entities across "
        f"{summary.total_edges} connections up to depth {summary.max_depth}.\n\n"
        f"Top risk contributors:\n{top_contributors}"
    )
