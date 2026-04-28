# TrustWeb — Full Implementation Plan

> Module C of the AML Scoring Pipeline.  
> Graph-based correlation engine that scores money-laundering risk by analyzing the network of connections between companies, people, and events.

---

## 1. Architecture Overview

TrustWeb is a **library module** (no HTTP API) that exposes one top-level function callable by the future Stage 3 orchestrator:

```
trust_web.score_firm(firm_id, pg_session) → TrustWebResult
```

### Key Architectural Principle

**Tarkov writes standalone nodes only.** It extracts entities (companies, people, events) from articles and stores them in Postgres. It does NOT create any Neo4j edges.

**TrustWeb creates all edges.** It reads Postgres data, creates standalone nodes in Neo4j, then uses LLM to analyze the source evidence and discover connections between entities. All edges in the graph are TrustWeb's responsibility.

### High-Level Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 1 — Graph Construction                                        │
│                                                                      │
│  Step 1: Read Postgres for all entities related to the target firm   │
│    ├── Firm + neighbor firms (from connection_entity hints)          │
│    ├── Events (classical, people, connection)                        │
│    ├── Persons (via person_event + firm_id)                          │
│    └── Source evidence texts (source_text_quote, article content)    │
│                                                                      │
│  Step 2: Create standalone Neo4j nodes for every entity              │
│    (Company, Person, Event — no edges)                               │
│                                                                      │
│  Step 3: LLM Edge Discovery                                         │
│    Feed all entities + source evidence to LLM →                      │
│    LLM returns a list of edges with:                                 │
│      - relationship type (CONNECTION, ABOUT, INVOLVED_IN, etc.)      │
│      - intensity (0.0–1.0)                                           │
│      - human-readable description                                    │
│                                                                      │
│  Step 4: Write LLM-discovered edges to Neo4j                        │
│                                                                      │
│  Fallback: When LLM is unavailable, create heuristic edges from     │
│  Postgres data (connection_entity hints, event→firm, person→firm)    │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ PHASE 2 — Risk Propagation & Scoring                                 │
│                                                                      │
│  1. Traverse graph from target firm node, depth ≤ 5 (configurable)   │
│  2. Collect subgraph: all reachable nodes + edges within depth       │
│  3. Run iterative risk-propagation algorithm:                        │
│       neighbor_risk × connection_intensity, decay by distance        │
│  4. Produce numeric TrustWeb score (0.0–1.0)                        │
│  5. Feed subgraph summary to LLM → human-readable risk explanation   │
│  6. Write score + explanation to database                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Package Structure

```
backend/trust_web/
├── __init__.py              # Public API: score_firm()
├── config.py                # TrustWebConfig dataclass (own LLM config + Neo4j + tuning params)
├── graph/
│   ├── __init__.py
│   ├── builder.py           # Phase 1: reads Postgres, creates nodes, LLM discovers edges
│   ├── queries.py           # Cypher query constants
│   └── traversal.py         # Phase 2 step 1-2: subgraph extraction from Neo4j
├── scoring/
│   ├── __init__.py
│   ├── intensity.py         # LLM edge discovery + intensity scoring + fallback heuristics
│   ├── propagation.py       # Iterative risk propagation algorithm
│   └── aggregator.py        # Final score computation from propagation results
├── llm/
│   ├── __init__.py
│   ├── client.py            # OpenRouter HTTP client (own config)
│   └── prompts.py           # Prompt templates for edge discovery, intensity, explanation
├── schemas.py               # Pydantic models: TrustWebResult, LLMEdge, EntityForDiscovery, etc.
└── tests/
    ├── __init__.py
    ├── test_builder.py
    ├── test_intensity.py
    ├── test_propagation.py
    └── test_aggregator.py
```

---

## 3. Configuration

Dataclass: `trust_web.config.TrustWebConfig`

| Env Variable | Default | Purpose |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` | `neo4j` | Neo4j auth user |
| `NEO4J_PASSWORD` | `trusttrace` | Neo4j auth password |
| `TRUSTWEB_LLM_API_KEY` | *(empty — fallback mode)* | OpenRouter API key for TrustWeb |
| `TRUSTWEB_LLM_MODEL` | `openai/gpt-4o-mini` | OpenRouter model for edge discovery + intensity |
| `TRUSTWEB_LLM_EXPLANATION_MODEL` | `openai/gpt-4o` | Model for final risk explanation |
| `TRUSTWEB_MAX_DEPTH` | `5` | Max graph traversal depth |
| `TRUSTWEB_DECAY_FACTOR` | `0.6` | Per-hop risk decay multiplier |
| `TRUSTWEB_PROPAGATION_ITERATIONS` | `10` | Max iterations for convergence |
| `TRUSTWEB_CONVERGENCE_THRESHOLD` | `0.001` | Stop iterating when max delta < this |
| `TRUSTWEB_INTENSITY_BATCH_SIZE` | `10` | Concurrent LLM calls |

---

## 4. Phase 1 — Graph Construction (`graph/builder.py`)

### 4.1 Entry Point

```python
async def build_graph_for_firm(firm_id: int, pg_session: Session, config: TrustWebConfig) -> GraphBuildResult
```

### 4.2 Step-by-Step

1. **Gather entities from Postgres:**
   - Load the target firm and all its events (classical, people, connection).
   - Load all persons linked via `person_event` rows and via `person.firm_id`.
   - Use `connection_entity` rows as **hints** to find neighbor firm IDs.
   - Load neighbor firms and their events/persons too.
   - Collect all `source_text_quote` and `source.content` as evidence texts.

2. **Create standalone Neo4j nodes:**
   - MERGE a node for each entity (Company, Person, Event).
   - No edges are created at this step.

3. **LLM edge discovery:**
   - Present all entities + evidence texts to the LLM.
   - LLM analyzes evidence and returns a JSON array of edges, each with:
     - `source_entity_id`, `target_entity_id`
     - `relationship_type` (CONNECTION, ABOUT, INVOLVED_IN, AFFILIATED_WITH)
     - `connection_subtype` (shared_director, business_relationship, etc.)
     - `intensity` (0.0–1.0)
     - `description` (human-readable, for frontend hover)

4. **Write edges to Neo4j:**
   - For each LLM-discovered edge, MERGE the appropriate relationship.

### 4.3 Fallback (No LLM)

When no LLM API key is configured, edges are created heuristically from Postgres data:
- `connection_entity` rows → CONNECTION edges (using `confidence` as intensity)
- `event.firm_id` → ABOUT edges (Company → Event)
- `person.firm_id` → AFFILIATED_WITH edges (Company → Person)

### 4.4 Idempotency

All Neo4j writes use `MERGE` keyed on stable identifiers (Postgres IDs + event IDs), so `build_graph_for_firm` can be called multiple times safely.

---

## 5. LLM Edge Discovery (`scoring/intensity.py`)

### 5.1 Purpose

Given a set of entities and source evidence, ask the LLM to:
1. Identify which entities are connected.
2. Determine the type and intensity of each connection.
3. Generate a human-readable description for each edge.

### 5.2 Input

```python
class EntityForDiscovery(BaseModel):
    entity_id: str
    entity_type: str  # "Company" | "Person" | "Event"
    name: str
    context: str = ""  # role, event_type, risk_level, etc.
```

### 5.3 Output

```python
class LLMEdge(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    connection_subtype: str | None
    intensity: float  # 0.0–1.0
    description: str
```

### 5.4 Prompt Design

The system prompt instructs the LLM to act as an AML analyst, analyze the evidence, and return a JSON array of connections. Only connections supported by evidence should be created.

### 5.5 Fallback

If the LLM call fails or no API key is configured:
- CONNECTION edges: created from `connection_entity` rows with `confidence` as intensity
- ABOUT edges: created from `event.firm_id` relationships
- AFFILIATED_WITH edges: created from `person.firm_id` relationships

---

## 6. Phase 2 — Subgraph Extraction (`graph/traversal.py`)

### 6.1 Subgraph Query

```cypher
MATCH path = (root:Company {company_id: $firm_id})-[*1..N]-(neighbor)
WITH root, neighbor, relationships(path) AS rels, length(path) AS depth
RETURN DISTINCT neighbor, labels(neighbor), edge_info, depth
ORDER BY depth
```

### 6.2 Risk Level Enrichment

After extracting the subgraph from Neo4j, enrich each node's `risk_level` from Postgres:
- Company nodes: latest `reputation_score.score`
- Event nodes: `event.risk_level / 10.0`
- Person nodes: no inherent risk (inherit via connections)

---

## 7. Risk Propagation Algorithm (`scoring/propagation.py`)

### 7.1 Attenuated Risk Diffusion

```
Initialize: risk[node] = node.risk_level or 0.0

Iterate until convergence:
  For each node n:
    For each neighbor m:
      contribution = risk[m] × edge_intensity × decay^depth
    propagated = weighted_mean(contributions)
    risk[n] = 0.7 × risk[n] + 0.3 × propagated

Output: risk[root_firm] = TrustWeb score
```

### 7.2 Edge Cases

- **Isolated firm** (no edges): score `0.0`, explanation "No network connections found."
- **Cyclic graphs**: handled naturally by convergence.

---

## 8. Final Score & Explanation (`scoring/aggregator.py`)

1. Run `propagate_risk()` → full risk map.
2. Extract root firm's score, clamp to [0, 1].
3. Build top-5 risk contributors list.
4. Ask LLM for human-readable explanation (or use deterministic template).

---

## 9. Database

### 9.1 Neo4j (Phase 1)

All nodes and edges created by TrustWeb. Tarkov does NOT write to Neo4j.

### 9.2 Postgres — `trustweb_score` table

```sql
CREATE TABLE trustweb_score (
    id              SERIAL PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    score           DECIMAL(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
    explanation     TEXT,
    node_count      INT,
    edge_count      INT,
    max_depth_used  INT,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 10. Public API (`__init__.py`)

```python
async def score_firm(
    firm_id: int,
    pg_session: Session,
    config: TrustWebConfig | None = None,
) -> TrustWebResult
```

---

## 11. Boundary Between Tarkov and TrustWeb

| Responsibility | Tarkov | TrustWeb |
|---|---|---|
| Extract entities from articles | ✅ | ❌ |
| Write firms, events, persons to Postgres | ✅ | ❌ |
| Write connection_entity hints to Postgres | ✅ | ❌ |
| Create Neo4j nodes | ❌ | ✅ |
| Create Neo4j edges | ❌ | ✅ |
| LLM-based edge discovery | ❌ | ✅ |
| Risk propagation scoring | ❌ | ✅ |
| LLM explanation generation | ❌ | ✅ |
