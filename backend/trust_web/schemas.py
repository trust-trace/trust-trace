"""Pydantic models for TrustWeb data flow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from timeline.buckets import TimelineBucket


# ── LLM edge discovery ─────────────────────────────────────────────────────

class EntityForDiscovery(BaseModel):
    """An entity (company/person/event) presented to the LLM for edge discovery."""
    entity_id: str
    entity_type: str  # "Company" | "Person" | "Event"
    name: str
    context: str = ""  # role, event_type, risk_level, etc.
    occurred_at: Optional[datetime] = None


class LLMEdge(BaseModel):
    """A connection discovered by the LLM between two entities."""
    source_entity_id: str
    target_entity_id: str
    relationship_type: str  # CONNECTION, ABOUT, INVOLVED_IN, AFFILIATED_WITH
    connection_subtype: Optional[str] = None
    intensity: float = Field(ge=0.0, le=1.0, default=0.5)
    description: str = ""


# ── Intensity scoring (for re-scoring individual edges) ────────────────────

class ConnectionForScoring(BaseModel):
    connection_type: str
    entity_1_name: str
    entity_1_type: str
    entity_2_name: str
    entity_2_type: str
    relationship_description: str = ""
    source_text_quote: str = ""


class IntensityResult(BaseModel):
    intensity: float = Field(ge=0.0, le=1.0)
    description: str = ""


# ── Subgraph ───────────────────────────────────────────────────────────────

class SubgraphNode(BaseModel):
    node_id: str
    node_type: str  # "Company" | "Person" | "Event"
    name: str
    depth: int
    risk_level: Optional[float] = None
    occurred_at: Optional[datetime] = None


class SubgraphEdge(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str  # CONNECTION, ABOUT, INVOLVED_IN, AFFILIATED_WITH
    intensity: Optional[float] = None
    connection_subtype: Optional[str] = None
    llm_description: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    event_occurred_at: Optional[datetime] = None


class SubgraphData(BaseModel):
    root_firm_id: int
    nodes: list[SubgraphNode] = Field(default_factory=list)
    edges: list[SubgraphEdge] = Field(default_factory=list)
    max_depth_reached: int = 0


# ── Propagation ────────────────────────────────────────────────────────────

class PropagationResult(BaseModel):
    risk_map: dict[str, float] = Field(default_factory=dict)
    iterations_run: int = 0
    converged: bool = False


# ── Final result ───────────────────────────────────────────────────────────

class SubgraphSummary(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    company_count: int = 0
    person_count: int = 0
    event_count: int = 0
    max_depth: int = 0


class GraphBuildResult(BaseModel):
    nodes_created: int = 0
    edges_created: int = 0
    llm_edges_discovered: int = 0
    fallback_edges_created: int = 0
    errors: list[str] = Field(default_factory=list)


class TrustWebResult(BaseModel):
    firm_id: int
    score: float = Field(ge=0.0, le=1.0)
    explanation: str = ""
    subgraph_summary: SubgraphSummary = Field(default_factory=SubgraphSummary)
    connections_scored: int = 0
    max_depth_used: int = 0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Timeline result types ──────────────────────────────────────────────────

class TrustWebTimelineEntry(BaseModel):
    bucket_index: int
    bucket_start: datetime
    bucket_end: datetime
    score: float = Field(ge=0.0, le=1.0)
    node_count: int = 0
    edge_count: int = 0
    max_depth_used: int = 0


class TrustWebTimelineResult(BaseModel):
    firm_id: int
    entries: list[TrustWebTimelineEntry]
    explanation: str = ""
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
