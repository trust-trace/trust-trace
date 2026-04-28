# Timeline Scoring — Implementation Plan

> Replace single-point scores with an 8-bucket historical timeline.
> Both EEM and TrustWeb produce `list[TimelineScore]` instead of a single number.

---

## 1. Core Concept

Today, both scoring modules output **one score per firm**:
- **EEM**: a single `int` (0–100) aggregated from all classical events
- **TrustWeb**: a single `float` (0.0–1.0) from graph propagation

The new behavior divides the firm's lifetime into **8 equal time periods** and produces a score for each period, giving a risk trajectory over the company's history.

### Timeline Construction

```
firm.created_at = 2018-03-15
today           = 2026-04-28
age             = 8 years, 1 month, 13 days  (≈ 2966 days)
increment       = 2966 / 8 = ~371 days

bucket_dates = [
    2018-03-15,   # T0 — founding
    2019-03-22,   # T1
    2020-03-27,   # T2
    2021-04-01,   # T3
    2022-04-07,   # T4
    2023-04-12,   # T5
    2024-04-17,   # T6
    2025-04-22,   # T7
]

Each bucket covers events from bucket_dates[i] to bucket_dates[i+1] (or today for the last one).
```

A 2-year-old company would get 8 buckets of ~91 days each.
A 16-year-old company would get 8 buckets of ~2 years each.

---

## 2. New Shared Module: `timeline`

Create `backend/timeline/` with the date-bucketing logic used by both EEM and TrustWeb.

### `backend/timeline/__init__.py`

```python
from timeline.buckets import compute_timeline_buckets, TimelineBucket
```

### `backend/timeline/buckets.py`

```python
@dataclass
class TimelineBucket:
    index: int            # 0–7
    start: datetime       # inclusive
    end: datetime         # exclusive (except last bucket: inclusive of today)
    label: str            # human-readable, e.g. "2019-03 → 2020-03"

def compute_timeline_buckets(
    firm_created_at: datetime,
    as_of: datetime | None = None,  # defaults to utcnow()
    n_buckets: int = 8,
) -> list[TimelineBucket]:
    """Divide the firm's lifetime into N equal buckets.

    Returns exactly `n_buckets` TimelineBucket objects.
    Bucket dates are rounded to the nearest day.
    """
```

This is a pure function — no DB, no LLM. Easy to unit test.

---

## 3. Schema: `firm` Table — Add `founded_at`

The `firm` table currently has `created_at` (row insertion time) but no business-level founding date. We need a `founded_at` column that represents when the company was actually incorporated/created in the real world.

### Migration: `003_firm_founded_at.sql`

```sql
ALTER TABLE firm ADD COLUMN founded_at DATETIME;


UPDATE firm SET founded_at = created_at WHERE founded_at IS NULL;
```

### ORM update: `tarkov/database/models.py`

Add `founded_at: Mapped[datetime | None]` to the `Firm` model.

### Timeline logic

When computing buckets:
- Use `firm.founded_at` if set
- Fall back to `firm.created_at` if `founded_at` is NULL
- The pipeline should always resolve this before calling into EEM/TrustWeb

---

## 4. EEM Changes

### 4.1 Current Flow (single score)

```
load_classical_events(firm_id)     → all events, ordered by occurred_at
for event in events:
    _analyze_event(event)          → LLM enrichment (unchanged)
    collect impact + keywords
_compute_score(all_impacts)        → single (score, risk, trend, history, keywords)
upsert firm_score                  → one row
```

### 4.2 New Flow (timeline)

```
buckets = compute_timeline_buckets(firm.founded_at)
events  = load_classical_events(firm_id)     # still all events

# Partition events into buckets by occurred_at
bucketed_events = assign_events_to_buckets(events, buckets)

for event in all_events:                     # LLM enrichment is still per-event
    _analyze_event(event)                    # no change — enrichment doesn't depend on buckets

# Score each bucket independently
timeline_scores = []
for i, bucket in enumerate(buckets):
    bucket_impacts = [impacts for events in bucketed_events[i]]
    score_i = _compute_score(bucket_impacts, ...)
    timeline_scores.append(score_i)
```

### 4.3 Files to Modify

| File | Change |
|------|--------|
| `eem/_pipeline.py` | `_run()` accepts buckets, partitions events, loops `_compute_score` per bucket. Return type changes from `float` to `list[dict]`. |
| `eem/_pipeline.py` | `_compute_score()` — no changes needed (already works on a list of impacts). Called once per bucket. |
| `eem/database/models.py` | New model `FirmScoreTimeline` or modify `FirmScore` to hold 8 scores (see §6). |
| `eem/database/_repos.py` | `_FirmScoreRepo` — new method `upsert_timeline()` that writes 8 rows. |
| `eem/__init__.py` | Update `enrich_firm` return type and signature. |
| `eem/main.py` | Update CLI output to show timeline. |

### 4.4 Bucket Assignment Logic

```python
def assign_events_to_buckets(
    events: list[_EventRow],
    buckets: list[TimelineBucket],
) -> list[list[_EventRow]]:
    """Assign each event to its nearest bucket by occurred_at."""
    result = [[] for _ in buckets]
    for event in events:
        # Find which bucket this event falls into
        for i, bucket in enumerate(buckets):
            if bucket.start <= event.occurred_at < bucket.end:
                result[i].append(event)
                break
        else:
            # Event after last bucket start → last bucket
            result[-1].append(event)
    return result
```

### 4.5 Empty Buckets

Buckets with no events get the **neutral score of 50** (same as current behavior for firms with no events). This is semantically correct: no evidence = neutral trust.

### 4.6 Cumulative vs. Snapshot Scoring

**Decision: Cumulative.** Each bucket's score is computed from **all events up to and including that bucket**, not just events within that bucket. This gives a trajectory where the score evolves as evidence accumulates, matching how an analyst would assess trust over time.

```python
for i, bucket in enumerate(buckets):
    # All events from founding through end of this bucket
    cumulative_events = [e for e in events if e.occurred_at < bucket.end]
    bucket_impacts = [impact_map[e.event_id] for e in cumulative_events]
    score_i = _compute_score(bucket_impacts, ...)
```

---

## 5. TrustWeb Changes

### 5.1 Current Flow (single score)

```
build_graph_for_firm(firm_id)          → Neo4j graph (all entities)
extract_subgraph(firm_id)              → SubgraphData
propagate_risk(subgraph)               → PropagationResult with risk_map
compute_trustweb_score(firm_id, ...)   → TrustWebResult (single score)
_persist_score(firm_id, result)        → one INSERT
```

### 5.2 New Flow (timeline)

The graph is built **once** from all data (graph structure doesn't change over time). The difference is in which **events and connections** are considered active at each point in time.

```
buckets = compute_timeline_buckets(firm.founded_at)

# Phase 1 — Graph construction (unchanged — builds from all data)
build_graph_for_firm(firm_id)

# Phase 2 — Score per bucket
timeline_scores = []
for i, bucket in enumerate(buckets):
    # Extract subgraph with only entities that existed by bucket.end
    subgraph_i = extract_subgraph(firm_id, cutoff_date=bucket.end)
    result_i   = compute_trustweb_score(firm_id, subgraph_i, ...)
    timeline_scores.append(result_i)
```

### 5.3 Date Availability Audit — What's Missing

**Problem: dates are dropped at multiple points in the TrustWeb pipeline.**
The plan says "filter the subgraph in Python per bucket" — but the in-memory
objects currently don't carry the dates needed for filtering. Here's a
layer-by-layer trace of where dates exist and where they're lost:

#### Layer 1: Postgres → `builder.py` (EntityForDiscovery)

`builder.py` reads `Event` ORM objects from Postgres. These have `occurred_at`.
But when creating `EntityForDiscovery`, `occurred_at` is **not** passed through:

```python
# Current — no date:
EntityForDiscovery(
    entity_id=event.unique_id,
    entity_type="Event",
    name=event.title,
    context=f"type={event.event_type}, category={event.event_category}, risk_level={event.risk_level}",
)
```

**Fix:** Either add `occurred_at` to the `context` string, or (better) add an
explicit `occurred_at: datetime | None` field to `EntityForDiscovery`.

#### Layer 2: `builder.py` → Neo4j nodes

`MERGE_EVENT_NODE` stores `title`, `risk_level`, `event_type` — **not `occurred_at`**:

```cypher
MERGE (e:Event {event_id: $event_id})
SET e.title = $title, e.risk_level = $risk_level, e.event_type = $event_type
```

**Fix:** Add `e.occurred_at = $occurred_at` to the Cypher SET clause.

#### Layer 3: Neo4j edges — CONNECTION has no event date

`MERGE_CONNECTION_EDGE` stores `source_event_id` and `scored_at` (the time
TrustWeb wrote the edge, not when the underlying event occurred):

```cypher
SET r.scored_at = datetime()
```

**Fix:** Add `r.event_occurred_at = $event_occurred_at` to the CONNECTION
edge SET clause. The builder can look up the event's `occurred_at` when
writing the edge.

#### Layer 4: Neo4j → `traversal.py` (SubgraphNode / SubgraphEdge)

`SubgraphNode` has `node_id`, `node_type`, `name`, `depth`, `risk_level` —
**no date field**. `SubgraphEdge` has `intensity`, `connection_subtype`, etc. —
**no date field**.

After extraction, `_enrich_risk_levels()` loops through nodes and queries
Postgres for `risk_level`, but **does not fetch `occurred_at`**.

**Fix:**
- Add `occurred_at: Optional[datetime] = None` to `SubgraphNode`.
- Add `event_occurred_at: Optional[datetime] = None` to `SubgraphEdge`.
- Update `_enrich_risk_levels()` to populate these from Postgres.
- Update `EXTRACT_SUBGRAPH` Cypher to return `e.occurred_at` for Event nodes
  and `r.event_occurred_at` for edges.

#### Layer 5: `_enrich_risk_levels()` — reputation_score needs cutoff

Currently uses `ORDER BY calculated_at DESC LIMIT 1` (latest reputation).
For timeline buckets, we need `WHERE calculated_at <= :cutoff` — "what was
the reputation score at that point in time?"

`reputation_score` already has `calculated_at`, so this query just needs
the cutoff parameter threaded through.

### 5.4 Recommended Approach: Extract Once, Filter in Python

Given the above, the cleanest strategy is:

1. **At graph-build time**, store `occurred_at` on Neo4j Event nodes and
   `event_occurred_at` on CONNECTION edges (small changes to `queries.py`
   and `builder.py`).

2. **At subgraph-extraction time**, pull `occurred_at` into the in-memory
   objects (`SubgraphNode.occurred_at`, `SubgraphEdge.event_occurred_at`).
   This requires updating `EXTRACT_SUBGRAPH` Cypher + the node/edge parsing
   in `traversal.py`.

3. **At scoring time**, extract the full subgraph **once**, then for each
   bucket, run a pure-Python filter that removes future nodes/edges:

```python
def filter_subgraph_by_cutoff(
    full_subgraph: SubgraphData,
    cutoff: datetime,
) -> SubgraphData:
    """Return a copy with only entities active by cutoff.

    No DB round-trip needed — dates are already on the in-memory objects.
    """
    # Keep: Company nodes (always), Event nodes with occurred_at <= cutoff,
    #        Person nodes whose linked events are <= cutoff
    # Keep: Edges where both endpoints survive AND event_occurred_at <= cutoff
```

4. **For reputation_score**, pass `cutoff` into `_enrich_risk_levels()` so
   the query becomes `WHERE calculated_at <= :cutoff ORDER BY calculated_at DESC LIMIT 1`.

This avoids 8 separate Neo4j extractions and 8× Postgres lookups.
The only extra cost is storing two datetime fields that aren't stored today.

### 5.5 Files to Modify

| File | Change |
|------|--------|
| `trust_web/schemas.py` | Add `occurred_at` to `SubgraphNode`, `event_occurred_at` to `SubgraphEdge`, add `TimelineResult` model. |
| `trust_web/graph/queries.py` | Add `occurred_at` to `MERGE_EVENT_NODE` SET. Add `event_occurred_at` to `MERGE_CONNECTION_EDGE` SET. Update `EXTRACT_SUBGRAPH` to return `occurred_at` on Event nodes and `event_occurred_at` on edges. |
| `trust_web/graph/builder.py` | Pass `event.occurred_at` when creating Event nodes and when writing CONNECTION edges. Add `occurred_at` to `EntityForDiscovery` (or the context string). |
| `trust_web/graph/traversal.py` | Parse `occurred_at` from Neo4j results into `SubgraphNode`. Parse `event_occurred_at` into `SubgraphEdge`. Add `cutoff` param to `_enrich_risk_levels()` for time-filtered reputation queries. Add `filter_subgraph_by_cutoff()`. |
| `trust_web/__init__.py` | `score_firm()` loops over buckets; returns `TrustWebTimelineResult`. Calls `filter_subgraph_by_cutoff()` per bucket. |
| `trust_web/scoring/aggregator.py` | No changes needed — called once per bucket. |
| `trust_web/scoring/propagation.py` | No changes needed — runs on whatever subgraph it receives. |
| `trust_web/__init__.py` | `_persist_score()` writes 8 rows (one per bucket) with a `bucket_index` column. |

### 5.5 LLM Explanation

Generate **one** explanation for the full timeline (not 8 separate ones). The explanation prompt gets the score trajectory as input so it can describe the trend.

```
"The firm's network risk evolved from 0.12 in 2019 to 0.67 in 2025, with a
sharp increase in 2023 when connections to sanctioned entities were discovered."
```

---

## 6. Database Changes

### 6.1 New Table: `firm_score_timeline`

Replaces the single `firm_score` row with 8 rows per scoring run.

```sql
CREATE TABLE firm_score_timeline (
    id              SERIAL PRIMARY KEY,
    firm_id         INT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL,              -- groups 8 rows from one scoring run
    bucket_index    SMALLINT NOT NULL,           -- 0–7
    bucket_start    TIMESTAMP NOT NULL,
    bucket_end      TIMESTAMP NOT NULL,
    score           INT NOT NULL,                -- 0–100 (EEM scale)
    risk            VARCHAR(10) NOT NULL,
    event_count     INT NOT NULL DEFAULT 0,      -- events in this bucket
    keywords        TEXT NOT NULL DEFAULT '[]',
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, bucket_index)
);

CREATE INDEX idx_fst_firm_id ON firm_score_timeline(firm_id);
CREATE INDEX idx_fst_run_id ON firm_score_timeline(run_id);
```

### 6.2 New Table: `trustweb_score_timeline`

Replaces per-run single rows with 8 rows per run.

```sql
CREATE TABLE trustweb_score_timeline (
    id              SERIAL PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL,
    bucket_index    SMALLINT NOT NULL,
    bucket_start    TIMESTAMP NOT NULL,
    bucket_end      TIMESTAMP NOT NULL,
    score           DECIMAL(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
    node_count      INT,
    edge_count      INT,
    max_depth_used  INT,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, bucket_index)
);

-- Keep a single explanation per run (not per bucket)
CREATE TABLE trustweb_run (
    run_id          UUID PRIMARY KEY,
    firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
    explanation     TEXT,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_twst_firm_id ON trustweb_score_timeline(firm_id);
CREATE INDEX idx_twst_run_id ON trustweb_score_timeline(run_id);
```

### 6.3 Backward Compatibility

Keep the old `firm_score` and `trustweb_score` tables for now. The new timeline tables exist alongside them. Once the frontend is updated, the old tables can be deprecated.

---

## 7. Return Types

### EEM

```python
@dataclass
class EEMTimelineEntry:
    bucket_index: int
    bucket_start: datetime
    bucket_end: datetime
    score: int                # 0–100
    risk: str                 # high/medium/low
    event_count: int
    keywords: list[str]

# enrich_firm(firm_id) → list[EEMTimelineEntry]  (length 8)
```

### TrustWeb

```python
class TrustWebTimelineEntry(BaseModel):
    bucket_index: int
    bucket_start: datetime
    bucket_end: datetime
    score: float              # 0.0–1.0
    node_count: int
    edge_count: int
    max_depth_used: int

class TrustWebTimelineResult(BaseModel):
    firm_id: int
    entries: list[TrustWebTimelineEntry]  # length 8
    explanation: str                       # one explanation for the whole trajectory
    computed_at: datetime
```

---

## 8. Implementation Order

| # | Task | Depends On | Estimate |
|---|------|------------|----------|
| 1 | Create `timeline/` module with `compute_timeline_buckets()` + tests | — | Small |
| 2 | Add `founded_at` to `Firm` model + migration | — | Small |
| 3 | Update `seed_mock_data.py` to set `founded_at` and spread events across years | 2 | Small |
| 4 | Create `firm_score_timeline` + `trustweb_score_timeline` tables (migration) | — | Small |
| 5 | **Thread dates through TrustWeb graph layer** (prerequisite for TrustWeb timeline) | — | Medium |
| 5a | Add `occurred_at` to `SubgraphNode`, `event_occurred_at` to `SubgraphEdge` in `schemas.py` | — | Small |
| 5b | Update `queries.py`: `MERGE_EVENT_NODE` stores `occurred_at`, `MERGE_CONNECTION_EDGE` stores `event_occurred_at`, `EXTRACT_SUBGRAPH` returns both | 5a | Small |
| 5c | Update `builder.py`: pass `occurred_at` when writing Event nodes and CONNECTION edges | 5b | Small |
| 5d | Update `traversal.py`: parse dates from Neo4j results, populate schema fields, add `cutoff` to `_enrich_risk_levels()` | 5a, 5b | Medium |
| 6 | Modify EEM `_pipeline.py` to partition events by bucket, score per bucket | 1 | Medium |
| 7 | Modify EEM `_repos.py` to write `firm_score_timeline` rows | 4, 6 | Small |
| 8 | Modify EEM `__init__.py` / `main.py` to expose timeline return type | 6, 7 | Small |
| 9 | Add `filter_subgraph_by_cutoff()` to TrustWeb `traversal.py` | 1, 5d | Medium |
| 10 | Modify TrustWeb `__init__.py` to loop buckets, score per bucket | 9 | Medium |
| 11 | Modify TrustWeb `_persist_score()` to write timeline rows | 4, 10 | Small |
| 12 | Update TrustWeb explanation prompt to describe trajectory | 10 | Small |
| 13 | Update `run_trustweb.py` to display timeline | 10, 11 | Small |
| 14 | Update EEM + TrustWeb tests | 6–12 | Medium |

---

## 9. Example Output

### EEM Timeline (Orion Capital Group, founded 2018-03-15)

```
Bucket  Period                  Score  Risk     Events
──────  ──────────────────────  ─────  ───────  ──────
T0      2018-03 → 2019-03        50   low         0
T1      2019-03 → 2020-03        50   low         0
T2      2020-03 → 2021-04        50   low         0
T3      2021-04 → 2022-04        50   low         0
T4      2022-04 → 2023-04        50   low         0
T5      2023-04 → 2024-04        50   low         0
T6      2024-04 → 2025-04        38   high        1
T7      2025-04 → 2026-04        28   high        2
```

### TrustWeb Timeline (same firm)

```
Bucket  Period                  Score   Nodes  Edges
──────  ──────────────────────  ──────  ─────  ─────
T0      2018-03 → 2019-03       0.000      1      0
T1      2019-03 → 2020-03       0.000      1      0
T2      2020-03 → 2021-04       0.000      1      0
T3      2021-04 → 2022-04       0.000      1      0
T4      2022-04 → 2023-04       0.000      1      0
T5      2023-04 → 2024-04       0.120      3      2
T6      2024-04 → 2025-04       0.450      7      8
T7      2025-04 → 2026-04       0.672     11     15
```

---

## 10. Key Design Decisions

1. **Cumulative scoring** — each bucket considers all evidence up to that point, not just events within the bucket. This produces a monotonically-informed trajectory (more data over time).

2. **Graph built once, filtered per bucket** — Neo4j graph construction is expensive (LLM calls). We build it once from all data, then filter the subgraph in Python per bucket. This avoids 8× LLM cost.

3. **8 buckets always** — even if the firm is 2 months old, we still produce 8 buckets (of ~7.5 days each). The number 8 is fixed for consistent frontend rendering.

4. **One explanation per run** — the LLM explanation covers the whole trajectory, not individual buckets. This is cheaper and more useful (describes trend evolution).

5. **`founded_at` vs `created_at`** — we add a real-world `founded_at` field. The DB `created_at` reflects when the row was inserted (could be yesterday for a 20-year-old company).

6. **Shared timeline module** — bucket computation lives in `timeline/` so both EEM and TrustWeb use identical bucket boundaries. A firm scored by both modules produces aligned timelines.
