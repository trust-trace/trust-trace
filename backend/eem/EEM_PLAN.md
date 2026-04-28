# EEM — Event Enrichment Module

## What this module does

1. Accepts a `firm_id`
2. Fetches all `event_category = 'classical'` events for that firm from PostgreSQL
3. Sends each event through an OpenRouter LLM to enrich it with display fields
4. Saves the enriched fields back to the DB as a side effect
5. Computes a single 0–100 trust score mathematically from the per-event impacts
6. Returns that score

---

## Public API

```python
# eem/__init__.py exports exactly this:
from eem import enrich_firm
```

### `enrich_firm(firm_id: int) -> float`

| | |
|---|---|
| **Input** | `firm_id` — integer PK from the `firm` table |
| **Output** | `float` in range `[0.0, 100.0]` — the AML trust score for the firm (higher = cleaner) |
| **Side effect** | Writes one row per event to `event_enrichment` (upsert). Writes/updates one row in `firm_score`. |
| **Raises** | `FirmNotFoundError` if `firm_id` has no row in `firm`. Propagates DB and HTTP errors. |

This is the only symbol that external callers ever import from `eem`.

---

## File Structure

```
backend/
└── eem/
    ├── __init__.py               # from eem._pipeline import _run; enrich_firm = _run
    ├── EEM_PLAN.md
    ├── config.py                 # env vars: OPENROUTER_API_KEY, EEM_MODEL, DATABASE_URL
    ├── main.py                   # CLI — python -m eem.main enrich --firm-id 42
    │
    ├── database/
    │   ├── __init__.py
    │   ├── session.py            # SessionLocal — same pattern as tarkov/database/session.py
    │   ├── models.py             # EventEnrichment + FirmScore ORM models
    │   └── _repos.py             # _EventReader, _EnrichmentRepo, _FirmScoreRepo
    │
    ├── llm/
    │   ├── __init__.py
    │   ├── _client.py            # thin wrapper over OpenRouter — same as rkr/llm/openrouter_client.py
    │   ├── _prompts.py           # SYSTEM_PROMPT constant + build_user_message()
    │   └── _analyzer.py         # _analyze_event(): calls LLM → returns _EventFields
    │
    ├── _pipeline.py              # _run() — the actual logic behind enrich_firm()
    │
    └── tests/
        ├── __init__.py
        ├── test_prompts.py
        ├── test_scoring.py
        └── fixtures/
            └── sample_events.json
```

---

## Data the LLM must fill in

Each event needs these fields populated — the frontend (`src/lib/data.ts`) renders all of them.

| Field | Type | Description |
|---|---|---|
| `sentiment` | float -1..1 | Tone of the event for the company |
| `impact` | float -10..10 | Signed impact on trust (negative = harmful) |
| `source_tier` | `'tier-1'`/`'tier-2'`/`'tier-3'` | Quality of the source |
| `keywords` | `list[str]` | 3–6 short Polish keywords |
| `excerpt` | `str` | 2–4 sentence Polish summary displayed as article excerpt |
| `entities` | `list[str]` | People and organisations involved |

The LLM is only asked for these 6 fields. Everything else (`headline`, `date`, `source`) is already in the DB.

---

## Score Formula

The firm score is computed entirely in Python — no maths delegated to the LLM.

```
per_event_score(event) = clamp(50 + impact * 5, 0, 100)

firm_score = round(mean(per_event_score(e) for e in enriched_events))
```

Where `impact` is the signed float the LLM returns for each event.

Examples:
- `impact = -8.4` → `per_event_score = clamp(50 - 42, 0, 100) = 8`
- `impact = +2.1` → `per_event_score = clamp(50 + 10.5, 0, 100) = 61`
- `impact =  0.0` → `per_event_score = 50`

A firm with no events returns `50.0` (neutral baseline).

---

## Database Schema (new tables)

### `event_enrichment`

One row per event. Written as a side effect of `enrich_firm`.

```sql
CREATE TABLE event_enrichment (
    id          SERIAL PRIMARY KEY,
    event_id    VARCHAR(36) NOT NULL UNIQUE
                REFERENCES event(unique_id) ON DELETE CASCADE,
    sentiment   FLOAT       NOT NULL,
    impact      FLOAT       NOT NULL,
    source_tier VARCHAR(10) NOT NULL,
    keywords    TEXT        NOT NULL DEFAULT '[]',  -- JSON array
    excerpt     TEXT        NOT NULL,
    entities    TEXT        NOT NULL DEFAULT '[]',  -- JSON array
    model_used  VARCHAR(80) NOT NULL,
    enriched_at TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `firm_score`

One row per firm. Updated every time `enrich_firm` runs.

```sql
CREATE TABLE firm_score (
    id            SERIAL PRIMARY KEY,
    firm_id       INT         NOT NULL UNIQUE
                  REFERENCES firm(id) ON DELETE CASCADE,
    score         INT         NOT NULL,              -- 0–100
    risk          VARCHAR(10) NOT NULL,              -- 'high'|'medium'|'low'
    trend         INT         NOT NULL DEFAULT 0,    -- delta vs previous score
    score_history TEXT        NOT NULL DEFAULT '[]', -- JSON array, last 12 values
    keywords      TEXT        NOT NULL DEFAULT '[]', -- top 6 keywords across all events
    computed_at   TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`risk` is derived from `score`:
- `score ≤ 40` → `'high'`
- `score ≤ 65` → `'medium'`
- `score > 65`  → `'low'`

---

## Internal Components

None of these are imported from outside the `eem` package.

---

### `database/_repos.py`

Three small repository classes in one file (they are trivial).

#### `_EventReader`

**`load_classical_events(firm_id: int) -> list[_EventRow]`**

| | |
|---|---|
| **Input** | `firm_id` |
| **Output** | All rows from `event` where `firm_id=?` and `event_category='classical'`, each joined with its `source` rows and `person_event→person` rows. Ordered `occurred_at ASC`. Returns `[]` if none exist. |
| **Raises** | `FirmNotFoundError` if the `firm` row does not exist. |

**`get_firm_name(firm_id: int) -> str`**

| | |
|---|---|
| **Input** | `firm_id` |
| **Output** | `firm.full_name` |
| **Raises** | `FirmNotFoundError` |

**`get_unprocessed_firm_ids() -> list[int]`**

| | |
|---|---|
| **Output** | `firm_id`s that have at least one classical event with no row in `event_enrichment`. Used by `enrich-all` CLI. |

---

#### `_EnrichmentRepo`

**`upsert(event_id: str, fields: _EventFields, model: str) -> None`**

| | |
|---|---|
| **Input** | Event UUID, the 6 enrichment fields from the LLM, model name |
| **Does** | Insert or update row in `event_enrichment` keyed on `event_id`. Serialises `keywords` and `entities` to JSON strings. Calls `db.flush()`. Caller commits. |

---

#### `_FirmScoreRepo`

**`get_history(firm_id: int) -> list[int]`**

| | |
|---|---|
| **Output** | Current `score_history` array, or `[]` if no row exists yet. |

**`upsert(firm_id: int, score: int, risk: str, trend: int, history: list[int], keywords: list[str]) -> None`**

| | |
|---|---|
| **Does** | Insert or update row in `firm_score` keyed on `firm_id`. Serialises arrays to JSON strings. Sets `computed_at = now()`. Calls `db.flush()`. Caller commits. |

---

### `llm/_client.py`

Direct copy of `rkr/llm/openrouter_client.py`. Reads `OPENROUTER_API_KEY` and `EEM_MODEL` from env.

**`chat_completion(messages: list[dict], *, temperature: float = 0.1) -> str`**

| | |
|---|---|
| **Input** | OpenAI-format messages list |
| **Output** | Raw content string from the model |
| **Raises** | `RuntimeError` if `OPENROUTER_API_KEY` is not set. `httpx.HTTPStatusError` on non-2xx. |

---

### `llm/_prompts.py`

**`SYSTEM_PROMPT: str`** — module-level constant, never changes at runtime.

**`build_user_message(event: _EventRow, firm_name: str) -> str`**

| | |
|---|---|
| **Input** | One assembled event row with its sources and people, plus the firm name |
| **Output** | Formatted string — the user turn sent to the LLM |
| **Does** | Formats firm name, event type, title, risk level, date, source quote, source excerpts (truncated to `EEM_SOURCE_EXCERPT_CHARS`), and people with roles. Pure function — no I/O. |

---

### `llm/_analyzer.py`

**`_analyze_event(event: _EventRow, firm_name: str) -> _EventFields`**

| | |
|---|---|
| **Input** | One event row with context, firm name |
| **Output** | `_EventFields` — the 6 enrichment fields |
| **Does** | Calls `build_user_message`. Calls `chat_completion([system, user])`. Calls `_parse_response`. Returns `_EventFields`. |
| **Raises** | `_ParseError` if JSON is invalid or a field is out of range. Caller (`_run`) catches this, logs it, and skips the event. |

**`_parse_response(raw: str) -> _EventFields`** (private)

| | |
|---|---|
| **Input** | Raw string from the model |
| **Output** | `_EventFields` |
| **Does** | `json.loads`. Validates: `sentiment` ∈ [-1,1], `impact` ∈ [-10,10], `source_tier` ∈ `{'tier-1','tier-2','tier-3'}`, `keywords` is `list[str]`, `excerpt` is non-empty `str`, `entities` is `list[str]`. |
| **Raises** | `_ParseError` on any failure. |

---

### `_pipeline.py`

**`_run(firm_id: int) -> float`**

| | |
|---|---|
| **Input** | `firm_id` |
| **Output** | `float` — the computed firm score |
| **Does** | Opens a DB session. Loads classical events via `_EventReader`. For each event: calls `_analyze_event` → calls `_EnrichmentRepo.upsert`. Collects `impact` values. Calls `_compute_score`. Calls `_FirmScoreRepo.upsert`. Commits. Returns `float(score)`. Events where `_analyze_event` raises `_ParseError` are logged and skipped. If no events survive returns `50.0`. |

**`_compute_score(impacts: list[float], previous_history: list[int], all_keywords: list[list[str]]) -> tuple[int, str, int, list[int], list[str]]`**

| | |
|---|---|
| **Input** | `impacts` — list of per-event impact floats; `previous_history` — existing score history; `all_keywords` — per-event keyword lists |
| **Output** | `(score, risk, trend, updated_history, top_keywords)` |
| **Does** | Applies `clamp(50 + impact * 5, 0, 100)` to each impact. Takes mean, rounds to int → `score`. Derives `risk` from thresholds. `trend = score - previous_history[-1]` (0 if history empty). Appends score to history, keeps last 12 values. Flattens and frequency-counts all keywords, returns top 6. Pure function — no I/O. |

---

### Internal types

```python
# defined in _pipeline.py or a small _types.py

@dataclass
class _SourceRow:
    title: str | None
    url: str
    published_at: datetime | None
    content_excerpt: str   # truncated to EEM_SOURCE_EXCERPT_CHARS

@dataclass
class _PersonRow:
    name: str
    role: str | None
    role_in_event: str | None

@dataclass
class _EventRow:
    event_id: str
    firm_id: int
    event_type: str
    title: str
    risk_level: int
    occurred_at: datetime
    source_text_quote: str | None
    sources: list[_SourceRow]
    people: list[_PersonRow]

@dataclass
class _EventFields:     # what the LLM fills in
    sentiment: float
    impact: float
    source_tier: str
    keywords: list[str]
    excerpt: str
    entities: list[str]
```

---

## LLM System Prompt

```
You are an AML (Anti-Money Laundering) event analyst.
Given a corporate event, return a JSON object with exactly these fields:

{
  "sentiment":   <float -1.0..1.0  — overall tone for the company>,
  "impact":      <float -10.0..10.0 — signed trust impact; negative = harmful>,
  "source_tier": <"tier-1" | "tier-2" | "tier-3">,
  "keywords":    [<3 to 6 short Polish keyword strings>],
  "excerpt":     "<2 to 4 sentence Polish summary for display on a risk dashboard>",
  "entities":    [<names of people and organisations involved>]
}

source_tier:
  tier-1 — major national press (Rzeczpospolita, Parkiet, Puls Biznesu, Gazeta Wyborcza)
  tier-2 — online business portals (Bankier.pl, Onet Biznes, TVN24 BiS, Money.pl)
  tier-3 — financial data aggregators, forums, secondary sources

Rules:
- Return ONLY the JSON object. No markdown fences, no explanation.
- excerpt must be in Polish, factual, suitable for a compliance dashboard.
- keywords must be in Polish.
```

---

## Config

```python
# config.py — reads from environment
OPENROUTER_API_KEY: str        # required
EEM_MODEL: str                 # default: "openai/gpt-4o-mini"
EEM_SOURCE_EXCERPT_CHARS: int  # default: 800
DATABASE_URL: str              # required — same Postgres instance as tarkov
```

## Implementation Order

| # | File | Why this order |
|---|------|----------------|
| 1 | `database/models.py` | defines the two new tables |
| 2 | `database/session.py` | SessionLocal — copy tarkov pattern |
| 3 | `database/_repos.py` | DB read/write — testable with SQLite in-memory |
| 4 | `llm/_client.py` | copy rkr/llm/openrouter_client.py |
| 5 | `llm/_prompts.py` | pure string logic — unit testable without network |
| 6 | `llm/_analyzer.py` | calls LLM + parse |
| 7 | `_pipeline.py` | `_run` + `_compute_score` |
| 8 | `config.py` | env vars |
| 9 | `__init__.py` | expose `enrich_firm = _run` |
| 10 | `main.py` | CLI |
| 11 | `tests/` | `test_scoring.py` for `_compute_score`, `test_prompts.py` for `build_user_message` |
