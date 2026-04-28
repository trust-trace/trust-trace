"""LLM-based edge discovery and connection intensity scoring."""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from trust_web.config import TrustWebConfig
from trust_web.llm.client import chat_completion, parse_json_response
from trust_web.llm.prompts import (
    EDGE_DISCOVERY_SYSTEM,
    EDGE_DISCOVERY_USER,
    INTENSITY_SCORING_SYSTEM,
    INTENSITY_SCORING_USER,
)
from trust_web.schemas import (
    ConnectionForScoring,
    EntityForDiscovery,
    IntensityResult,
    LLMEdge,
)

logger = logging.getLogger(__name__)


async def discover_edges(
    firm_id: int,
    firm_name: str,
    entities: list[EntityForDiscovery],
    evidence_texts: list[str],
    config: TrustWebConfig,
) -> list[LLMEdge]:
    """Ask the LLM to discover connections between entities based on evidence.

    Falls back to heuristic edge creation when LLM is unavailable.
    """
    if not entities:
        return []

    entities_str = "\n".join(
        f"- [{e.entity_type}] ID={e.entity_id}, Name={e.name}"
        + (f", Context: {e.context}" if e.context else "")
        for e in entities
    )

    evidence_str = "\n---\n".join(evidence_texts) if evidence_texts else "(no source evidence available)"

    user_msg = EDGE_DISCOVERY_USER.format(
        firm_name=firm_name,
        firm_id=firm_id,
        entities_list=entities_str,
        evidence_text=evidence_str,
    )

    messages = [
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    raw = await chat_completion(messages, config, max_tokens=2000)
    parsed = parse_json_response(raw)

    if isinstance(parsed, list):
        valid_ids = {e.entity_id for e in entities}
        edges: list[LLMEdge] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            src = str(item.get("source_entity_id", ""))
            tgt = str(item.get("target_entity_id", ""))
            if src not in valid_ids or tgt not in valid_ids:
                logger.debug("LLM returned edge with unknown entity ID: %s -> %s", src, tgt)
                continue
            rel_type = item.get("relationship_type", "CONNECTION")
            if rel_type not in ("CONNECTION", "ABOUT", "INVOLVED_IN", "AFFILIATED_WITH"):
                rel_type = "CONNECTION"
            edges.append(LLMEdge(
                source_entity_id=src,
                target_entity_id=tgt,
                relationship_type=rel_type,
                connection_subtype=item.get("connection_subtype"),
                intensity=max(0.0, min(1.0, float(item.get("intensity", 0.5)))),
                description=str(item.get("description", "")),
            ))
        return edges

    logger.warning(
        "⚠️  LLM edge discovery returned no usable data — using FALLBACK heuristics. "
        "Edges will be created mechanically from Postgres hints, NOT from LLM analysis. "
        "Set TRUSTWEB_LLM_API_KEY to an OpenRouter key for real edge discovery."
    )
    return []


def build_fallback_edges(
    firm_id: int,
    entities: list[EntityForDiscovery],
    events_by_firm: dict[str, list[str]],
    persons_by_firm: dict[str, list[str]],
    connection_hints: list[dict],
) -> list[LLMEdge]:
    """Create edges heuristically when LLM is unavailable.

    Uses Postgres data as hints:
    - connection_entity rows → CONNECTION edges with 0.5 intensity
    - person_event rows → INVOLVED_IN edges
    - person.firm_id → AFFILIATED_WITH edges
    - event.firm_id → ABOUT edges
    """
    edges: list[LLMEdge] = []
    valid_ids = {e.entity_id for e in entities}
    firm_id_str = str(firm_id)

    for hint in connection_hints:
        src = str(hint["entity_1_id"])
        tgt = str(hint["entity_2_id"])
        if src in valid_ids and tgt in valid_ids:
            edges.append(LLMEdge(
                source_entity_id=src,
                target_entity_id=tgt,
                relationship_type="CONNECTION",
                connection_subtype=hint.get("connection_type"),
                intensity=float(hint.get("confidence", 0.5)),
                description=hint.get("relationship_description", ""),
            ))

    for f_id, event_ids in events_by_firm.items():
        if f_id not in valid_ids:
            continue
        for eid in event_ids:
            if eid in valid_ids:
                edges.append(LLMEdge(
                    source_entity_id=f_id,
                    target_entity_id=eid,
                    relationship_type="ABOUT",
                    intensity=0.8,
                    description="Company is the subject of this event",
                ))

    for f_id, person_ids in persons_by_firm.items():
        if f_id not in valid_ids:
            continue
        for pid in person_ids:
            if pid in valid_ids:
                edges.append(LLMEdge(
                    source_entity_id=f_id,
                    target_entity_id=pid,
                    relationship_type="AFFILIATED_WITH",
                    intensity=0.6,
                    description="Person is affiliated with this company",
                ))

    return edges


# ── Single-edge intensity re-scoring (kept for targeted rescoring) ─────────

async def score_connection(
    conn: ConnectionForScoring,
    config: TrustWebConfig,
) -> IntensityResult:
    """Score a single connection's intensity via LLM."""
    user_msg = INTENSITY_SCORING_USER.format(
        connection_type=conn.connection_type,
        entity_1_name=conn.entity_1_name,
        entity_1_type=conn.entity_1_type,
        entity_2_name=conn.entity_2_name,
        entity_2_type=conn.entity_2_type,
        relationship_description=conn.relationship_description,
        source_text_quote=conn.source_text_quote,
    )

    messages = [
        {"role": "system", "content": INTENSITY_SCORING_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    raw = await chat_completion(messages, config)
    parsed = parse_json_response(raw)

    if isinstance(parsed, dict) and "intensity" in parsed:
        intensity = max(0.0, min(1.0, float(parsed["intensity"])))
        description = str(parsed.get("description", ""))
        return IntensityResult(intensity=intensity, description=description)

    return _fallback_result(conn)


async def score_connections_batch(
    connections: Sequence[ConnectionForScoring],
    config: TrustWebConfig,
) -> list[IntensityResult]:
    """Score connections in parallel batches."""
    results: list[IntensityResult] = []
    batch_size = config.intensity_batch_size

    for i in range(0, len(connections), batch_size):
        batch = connections[i : i + batch_size]
        batch_results = await asyncio.gather(
            *[score_connection(c, config) for c in batch],
            return_exceptions=True,
        )
        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.warning("Intensity scoring failed for batch item %d: %s", i + j, result)
                results.append(_fallback_result(batch[j]))
            else:
                results.append(result)

    return results


def _fallback_result(conn: ConnectionForScoring) -> IntensityResult:
    """Produce a fallback intensity when LLM is unavailable."""
    description = conn.relationship_description
    if not description:
        description = (
            f"{conn.entity_1_name} connected to {conn.entity_2_name} "
            f"via {conn.connection_type}"
        )
    return IntensityResult(intensity=0.5, description=description)
