# Timeline And TradingView Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current hardcoded score-history timeline with backend-fed timeline data, add graceful fallback behavior when timeline data is unavailable, and enable TradingView only when the backend can provide a valid market symbol.

**Architecture:** Keep the existing Next proxy boundary. Extend the backend `/api/companies` contract to return timeline-ready history from real persisted timeline sources, with deterministic fallback order. Add explicit market identifier fields to the firm model so the frontend can render TradingView when available and disable the checkbox when not.

**Tech Stack:** Next.js app router, React, FastAPI, SQLAlchemy, existing Tarkov/EEM/Pipeline models, Vitest, Pytest

---

## Current State

- Frontend timeline UI is the score-history chart in `frontend/src/components/main-panel.tsx` and `frontend/src/components/score-chart.tsx`.
- The chart currently renders `company.history`.
- The TradingView toggle exists already in `frontend/src/components/main-panel.tsx`, but it is always enabled and uses a hardcoded symbol: `GPW:CDR`.
- Backend `/api/companies` is served by `backend/tarkov/frontend_graph_api.py`.
- Backend currently derives `history` from `FirmScore.score_history`, not from timeline tables.
- Timeline tables/models already exist in the repo:
  - `backend/eem/database/models.py` -> `FirmScoreTimeline`
  - `backend/pipeline/models.py` -> `FinalScoreTimeline`
  - `backend/trust_web/schemas.py` -> TrustWeb timeline types
- `Firm` currently has no explicit exchange/symbol fields.
- Ticker may exist only as a `FirmAlias` of type `ticker`, which is not enough for TradingView because exchange is also needed.

## Target Behavior

### Timeline
- The frontend timeline should come from backend data, not frontend mock arrays.
- Preferred backend source order:
  1. `final_score_timeline`
  2. `firm_score_timeline`
  3. `firm_score.score_history`
  4. safe generated fallback based on current score when no historical data exists
- The frontend should not crash if history is short, empty, or missing.
- The time-range tabs (`12M`, `6M`, `3M`, `30D`) should use real filtered backend-fed timeline data or a backend-supplied derived history set.

### TradingView
- If the backend can provide a valid TradingView symbol, enable the checkbox and render the widget with that symbol.
- If the backend cannot provide a valid symbol, the checkbox should be disabled and visually blocked.
- The backend should store market identifiers explicitly, because ticker aliases alone do not identify exchange.

---

## File Map

### Backend
- Modify: `backend/tarkov/database/models.py`
  - Add explicit market identifier fields on `Firm`
- Modify: `backend/tarkov/database/repositories/firm_repo.py`
  - Support writing missing market identifier fields
- Modify: `backend/tarkov/frontend_graph_api.py`
  - Build timeline/history from persisted timeline tables with fallback order
  - Add TradingView readiness fields to company payload
- Modify: `backend/tarkov/api.py`
  - No new route required if `/api/companies` stays the source of truth
- Create: `backend/tarkov/tests/test_frontend_timeline_api.py`
  - Focused backend contract tests for timeline and TradingView payload behavior
- Modify: `backend/tarkov/tests/test_frontend_graph_api.py`
  - Extend existing `/api/companies` contract coverage
- Optional create: `backend/tarkov/database/migrations/<new migration>.sql`
  - Add explicit firm market fields if this repo uses raw SQL migrations outside Alembic

### Frontend
- Modify: `frontend/src/lib/data.ts`
  - Extend `Company` type with optional market/timeline metadata fields
- Modify: `frontend/src/lib/api.ts`
  - No API shape change in fetch functions, only type surface if contract expands
- Modify: `frontend/src/components/main-panel.tsx`
  - Drive TradingView toggle from backend availability instead of hardcoded symbol
  - Use real filtered timeline series per selected tab
- Modify: `frontend/src/components/score-chart.tsx`
  - Handle shorter series and optional labels more safely
- Modify: `frontend/src/lib/api.test.ts`
  - Contract tests for expanded company payload
- Create: `frontend/src/components/main-panel.test.tsx`
  - Checkbox disabled/enabled behavior and timeline fallback rendering

---

## Backend Contract Shape

Extend each company object returned by `/api/companies` from:

```ts
{
  id,
  name,
  short,
  nip,
  sector,
  score,
  trend,
  risk,
  articles,
  lastUpdate,
  history,
  keywords
}
```

to:

```ts
{
  id,
  name,
  short,
  nip,
  sector,
  score,
  trend,
  risk,
  articles,
  lastUpdate,
  history,
  keywords,
  tradingViewSymbol?: string,
  hasTradingView?: boolean,
  historyByRange?: {
    "12M": number[],
    "6M": number[],
    "3M": number[],
    "30D": number[]
  }
}
```

Notes:
- Keep `history` for backward compatibility and existing sidebar/chart usage.
- `historyByRange` lets the current UI tabs become real without inventing frontend slicing rules.
- `tradingViewSymbol` should be a ready-to-use string like `GPW:CDR`.
- `hasTradingView` avoids forcing the frontend to infer availability from partial fields.

---

## Data Rules

### Timeline Fallback Rules
For each firm:
1. If `final_score_timeline` rows exist, use them.
2. Else if `firm_score_timeline` rows exist, use them.
3. Else if `firm_score.score_history` exists, use it.
4. Else derive a safe fallback:
   - a flat or gently repeated series based on the current score
   - never empty
   - same length expected by the active chart mode

### TradingView Rules
- Valid TradingView requires both:
  - exchange code
  - ticker/symbol
- Backend should emit:
  - `tradingViewSymbol = "${exchange}:${ticker}"`
  - `hasTradingView = true`
- If either is missing:
  - `tradingViewSymbol = ""`
  - `hasTradingView = false`

---

## Schema Decision

Use explicit nullable columns on `Firm` instead of only alias rows.

Recommended fields:
- `market_ticker`
- `market_exchange`

Reason:
- `FirmAlias` is good for matching and ingestion.
- TradingView needs structured display/runtime fields.
- `ticker` alias without exchange is ambiguous and not sufficient.
- Storing explicit fields avoids fragile lookup heuristics at render time.

---

## Task 1: Add Focused Backend Contract Tests

**Files:**
- Modify: `backend/tarkov/tests/test_frontend_graph_api.py`
- Create: `backend/tarkov/tests/test_frontend_timeline_api.py`

- [ ] **Step 1: Write failing tests for `/api/companies` timeline source priority**

```python
def test_company_history_prefers_final_score_timeline(...):
    ...

def test_company_history_falls_back_to_firm_score_timeline(...):
    ...

def test_company_history_falls_back_to_score_history(...):
    ...

def test_company_history_falls_back_to_safe_generated_series(...):
    ...
```

- [ ] **Step 2: Write failing tests for TradingView availability**

```python
def test_company_payload_includes_tradingview_symbol_when_exchange_and_ticker_exist(...):
    ...

def test_company_payload_blocks_tradingview_when_market_fields_missing(...):
    ...
```

- [ ] **Step 3: Run tests to verify failure**

Run:
`pytest backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py -q`

Expected:
- FAIL because market fields are missing and timeline selection logic does not exist

- [ ] **Step 4: Commit test-only changes**

```bash
git add backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py
git commit -m "test: cover timeline and tradingview company payloads"
```

---

## Task 2: Add Firm Market Identifier Storage

**Files:**
- Modify: `backend/tarkov/database/models.py`
- Modify: `backend/tarkov/database/repositories/firm_repo.py`
- Create or Modify: schema migration file for `firm`

- [ ] **Step 1: Add failing repository/model tests**

Add tests that prove:
- firm can store `market_ticker`
- firm can store `market_exchange`
- existing firm rows can be updated only when missing

- [ ] **Step 2: Run failing test subset**

Run:
`pytest backend/tarkov/tests -q -k "market_ticker or market_exchange or firm_repo"`

Expected:
- FAIL because the fields do not exist yet

- [ ] **Step 3: Implement schema change**

Add nullable fields to `Firm`:
- `market_ticker`
- `market_exchange`

- [ ] **Step 4: Implement repository update method**

Extend `update_missing_fields(...)` or add a focused method so ingestion/post-enrichment can write:

```python
market_ticker: str | None = None
market_exchange: str | None = None
```

- [ ] **Step 5: Run tests again**

Run:
`pytest backend/tarkov/tests -q -k "market_ticker or market_exchange or firm_repo"`

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tarkov/database/models.py backend/tarkov/database/repositories/firm_repo.py
git commit -m "feat: add firm market identifier fields"
```

---

## Task 3: Teach Backend `/api/companies` To Build Real Timeline Data

**Files:**
- Modify: `backend/tarkov/frontend_graph_api.py`
- Read: `backend/eem/database/models.py`
- Read: `backend/pipeline/models.py`

- [ ] **Step 1: Add a helper contract test for normalized timeline extraction**

Test for helper behavior:
- sorts timeline rows by `bucket_index`
- converts scores to chart-ready numeric arrays
- derives 12M/6M/3M/30D arrays deterministically

- [ ] **Step 2: Run tests to verify failure**

Run:
`pytest backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py -q`

Expected:
- FAIL because helper logic does not exist

- [ ] **Step 3: Implement timeline reader helpers in `FrontendGraphService`**

Add helpers with narrow responsibilities:
- load final timeline rows for firm ids
- load EEM timeline rows for firm ids
- normalize rows into arrays
- compute fallback arrays

Suggested helper names:
- `_load_final_score_timelines`
- `_load_eem_score_timelines`
- `_build_history_payload`

- [ ] **Step 4: Make `list_companies()` emit**
  - `history`
  - `historyByRange`
  - `tradingViewSymbol`
  - `hasTradingView`

- [ ] **Step 5: Keep existing fields unchanged**
  - no breaking changes to current frontend payload keys
  - `history` remains present

- [ ] **Step 6: Run backend contract tests**

Run:
`pytest backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py -q`

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add backend/tarkov/frontend_graph_api.py backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py
git commit -m "feat: serve timeline and tradingview metadata from companies api"
```

---

## Task 4: Surface Missing Market Data Into Enrichment Flow

**Files:**
- Modify: `backend/tarkov/extraction/company_matcher.py`
- Modify: `backend/tarkov/pipeline/processor.py`
- Modify: any post-firm-enrichment service if present
- Read: `backend/E2E_PIPELINE.md`

- [ ] **Step 1: Add failing tests proving ticker-only ingestion is insufficient**

Cases:
- ticker alias exists but no exchange -> TradingView blocked
- ticker and exchange both provided -> TradingView enabled
- missing both -> blocked

- [ ] **Step 2: Add/update firm enrichment path**
  - if article/reference data contains ticker only, persist `market_ticker`
  - if enrichment/reference data later yields exchange, persist `market_exchange`
  - never overwrite existing explicit market fields with blanks

- [ ] **Step 3: Run targeted tests**

Run:
`pytest backend/tarkov/tests -q -k "company_matcher or tradingview or market"`

Expected:
- PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tarkov/extraction/company_matcher.py backend/tarkov/pipeline/processor.py
git commit -m "feat: persist market identifiers for frontend tradingview"
```

---

## Task 5: Update Frontend Types And Toggle Behavior

**Files:**
- Modify: `frontend/src/lib/data.ts`
- Modify: `frontend/src/components/main-panel.tsx`
- Modify: `frontend/src/components/tradingview-widget.tsx`

- [ ] **Step 1: Write failing frontend tests**

Add tests that verify:
- checkbox is disabled when `hasTradingView === false`
- checkbox is enabled when `hasTradingView === true`
- widget receives backend `tradingViewSymbol`
- chart uses selected range instead of inert tabs

- [ ] **Step 2: Run tests to verify failure**

Run:
`npm test`

Expected:
- FAIL because the component still hardcodes `GPW:CDR` and tabs are inert

- [ ] **Step 3: Extend `Company` type**

Add optional fields:
- `tradingViewSymbol?: string`
- `hasTradingView?: boolean`
- `historyByRange?: { "12M": number[]; "6M": number[]; "3M": number[]; "30D": number[] }`

- [ ] **Step 4: Update `main-panel.tsx`**
  - derive displayed chart series from `activeTab`
  - disable checkbox if `!company.hasTradingView`
  - do not allow `showTVChart` to stay on when the company lacks symbol
  - replace hardcoded `GPW:CDR` with `company.tradingViewSymbol`

- [ ] **Step 5: Keep `TradingViewWidget` simple**
  - keep `symbol` as a required prop in usage
  - no internal fallback hardcoded symbol in the component path used by production UI

- [ ] **Step 6: Run frontend tests**

Run:
`npm test`

Expected:
- PASS

- [ ] **Step 7: Build frontend**

Run:
`npm run build`

Expected:
- PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/data.ts frontend/src/components/main-panel.tsx frontend/src/components/tradingview-widget.tsx
git commit -m "feat: wire timeline tabs and tradingview availability to backend data"
```

---

## Task 6: Add End-To-End API Coverage

**Files:**
- Modify: `backend/tarkov/tests/test_api.py`
- Optionally create: `frontend/src/components/main-panel.test.tsx`

- [ ] **Step 1: Add API-level tests**
  - `/api/companies` returns `history` from final timeline when present
  - `/api/companies` returns `history` fallback when timeline missing
  - `/api/companies` returns `hasTradingView=false` when exchange/ticker missing
  - `/api/companies` returns `tradingViewSymbol="EXCHANGE:TICKER"` when fields exist

- [ ] **Step 2: Run targeted tests**

Run:
`pytest backend/tarkov/tests/test_api.py -q -k "companies or tradingview or timeline"`

Expected:
- PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tarkov/tests/test_api.py
git commit -m "test: cover timeline and tradingview companies endpoint behavior"
```

---

## Task 7: Verification Pass

**Files:**
- No new files

- [ ] **Step 1: Run backend timeline contract tests**

Run:
`pytest backend/tarkov/tests/test_frontend_graph_api.py backend/tarkov/tests/test_frontend_timeline_api.py -q`

Expected:
- PASS

- [ ] **Step 2: Run frontend tests**

Run:
`npm test --prefix frontend`

Expected:
- PASS

- [ ] **Step 3: Run frontend build**

Run:
`npm run build --prefix frontend`

Expected:
- PASS

- [ ] **Step 4: Run a narrow API smoke test if dev server is available**

Example checks:
- `/api/companies` contains `history`
- `historyByRange["12M"]` exists
- `hasTradingView` false when symbol missing
- `tradingViewSymbol` present when available

- [ ] **Step 5: Final commit**

```bash
git status --short
```

Confirm only intended files changed before any final branch integration step.

---

## Implementation Notes

### Timeline Source Priority
Use this exact order in code:
1. `FinalScoreTimeline`
2. `FirmScoreTimeline`
3. `FirmScore.score_history`
4. generated fallback

### Generated Fallback
If no historical rows exist:
- return a non-empty array
- default length should match chart expectations
- use current score if present
- use stable deterministic values, not random numbers

### TradingView Checkbox UX
Recommended blocked state:
- `disabled={true}`
- muted styling
- short helper text like:
  - `Brak symbolu giełdowego w danych backendu`

### Avoid
- deriving exchange from country
- hardcoding `GPW:CDR`
- relying only on `FirmAlias(alias_type="ticker")`
- returning empty `history` arrays to the current chart

---

## Open Assumptions

- This plan assumes the existing timeline tables are available in the active database or can be created via the project’s schema path.
- This plan assumes frontend should keep the current `Company` payload and evolve it additively.
- This plan assumes “block the checkbox” means disabled, not hidden.

---

## Self-Review

- Spec coverage:
  - backend-fed timeline: covered
  - fallback when timeline missing: covered
  - TradingView only when backend has market code: covered
  - market code persistence if absent in DB schema: covered
- Placeholder scan:
  - no TODO/TBD placeholders
- Type consistency:
  - `history`, `historyByRange`, `tradingViewSymbol`, `hasTradingView` used consistently

---

## Handoff

When write access is available, save this plan as:

`docs/superpowers/plans/2026-04-28-timeline-and-tradingview.md`
```

If you want, I can next trim this plan down or start implementing it.
