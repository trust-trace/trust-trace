# Trace Feature — Frontend Implementation Spec

## Context

Every LLM/classifier decision in the pipeline is already persisted in the `reasoning_traces` Postgres table. Four classifiers write traces: **EEM** (event evaluation), **NSA** (person scoring), **Tarkov** (event extraction), and **Market** (ticker/data fetching). The backend already exposes REST endpoints to query these traces. The frontend has **zero** trace-related code today.

This spec describes what to build so users can inspect the reasoning behind every score, event, and decision the system produces.

---

## Backend API (already exists — no backend changes needed)

### Tarkov API (port 8081)

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/v1/traces/correlation/{correlationId}` | All traces linked to a correlation ID |
| `GET` | `/api/v1/traces/{classifier}/{entityId}` | Traces for a specific classifier + entity |

### NSA API (port 8082, if deployed separately)

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/score/traces/correlation/{correlationId}` | Same shape, from NSA service |
| `GET` | `/score/traces/{entityId}?classifier=X` | Traces by entity, optionally filtered |

### Response shape (per item)

Every item returned is a `ReasoningTraceStorageModel`:

```json
{
  "classifier_name": "EEM" | "NSA" | "Tarkov" | "Market",
  "entity_type": "event" | "person" | "event_extraction" | "company",
  "entity_id": "some-entity-id",
  "correlation_id": "optional-correlation-id",
  "trace_data": { /* domain-specific, see §Trace Shapes below */ },
  "created_at": "2026-04-27T14:32:00"
}
```

---

## Trace Shapes (what lives inside `trace_data`)

### EEM (`classifier_name: "EEM"`)

```typescript
interface EEMTraceData {
  model_used: "llm" | "deterministic";
  fallback_reason: string | null;
  sentiment_calculation: {
    base_sentiment: number;
    event_type: string;
    keyword_influences: string[];
    final_sentiment: number;
  };
  impact_scoring: {
    baseline_impact: number;
    risk_level: number;
    keyword_boost: number;
    final_impact: number;
  };
  source_tier_logic: {
    tier_assigned: string;
    authority_indicators: string[];
    reasoning: string;
  };
  keyword_extraction: {
    extracted_keywords: string[];
    dedup_count: number;
    top_6_keywords: string[];
  };
}
```

### NSA (`classifier_name: "NSA"`)

```typescript
interface NSATraceData {
  evidence_summary: {
    total_evidence_count: number;
    evidence_by_source: Record<string, number>;
    evidence_by_claim_type: Record<string, number>;
  };
  scoring_breakdown: Array<{
    evidence_id: number;
    source_kind: string;
    claim_type: string;
    claim_weight: number;
    source_multiplier: number;
    severity: number;
    confidence: number;
    official_bonus: number;
    contribution_to_score: number;
  }>;
  aggregation_logic: {
    raw_score: number;
    clamped_score: number;
    news_only_cap_applied: boolean;
    news_only_cap_value: number | null;
  };
  person_context: {
    person_id: number;
    person_name: string;
    role: string | null;
    evidence_sources_hit: string[];
  };
}
```

### Tarkov (`classifier_name: "Tarkov"`)

```typescript
interface TarkovTraceData {
  extraction_method: "keyword_based" | "llm_based";
  keyword_matching: {
    event_type: string;
    keywords_searched: string[];
    keywords_found: string[];
    hit_sentences: string[];
    deduped_hit_count: number;
  };
  confidence_calculation: {
    base_confidence: number;
    keyword_count: number;
    keyword_boost: number;
    final_confidence: number;
  };
  risk_level_assignment: {
    event_type: string;
    baseline_risk: number;
    keyword_count: number;
    boost_value: number;
    final_risk_level: number;
  };
  title_generation: {
    article_title: string;
    template_used: string | null;
    generated_title: string;
  };
  source_reference: {
    url: string;
    source_title: string;
    credibility_score: number;
    language: string;
    published_at: string | null;
  };
}
```

### Market (`classifier_name: "Market"`)

```typescript
interface MarketTraceData {
  ticker_search: {
    firm_name: string;
    search_strategy: "exact" | "fuzzy" | "partial";
    candidates_found: number;
    matching_process: Array<{
      candidate_name: string;
      ticker: string;
      exchange: string;
      match_score: number;
      selected: boolean;
      reason: string;
    }>;
  };
  listing_selection: {
    listings_considered: number;
    selected_listings: Array<{
      tv_symbol: string;
      tv_exchange: string;
      ticker: string;
      exchange: string;
    }>;
  };
  fetch_results: {
    listings_processed: number;
    successful_fetches: number;
    failed_fetches: number;
    by_listing: Array<{
      tv_symbol: string;
      tv_exchange: string;
      bars_fetched: number;
      bars_persisted: number;
      data_completeness: number;
      error: string | null;
    }>;
  };
  fetch_parameters: {
    n_bars_requested: number;
    date_range: {
      start_date: string | null;
      end_date: string | null;
      days_back: number;
    };
  };
}
```

---

## What to Build

### 1. Next.js API proxy routes

Create BFF proxy routes following the existing pattern in `src/app/api/` that forward to the backend via `proxyBackendJson`.

**Files to create:**

- `src/app/api/traces/correlation/[correlationId]/route.ts`

  ```typescript
  // GET /api/traces/correlation/:correlationId
  // Proxies to: /api/v1/traces/correlation/:correlationId
  ```

- `src/app/api/traces/[classifier]/[entityId]/route.ts`

  ```typescript
  // GET /api/traces/:classifier/:entityId
  // Proxies to: /api/v1/traces/:classifier/:entityId
  ```

### 2. TypeScript types (`src/lib/data.ts`)

Add to the existing `data.ts` file:

```typescript
export interface ReasoningTrace {
  classifier_name: "EEM" | "NSA" | "Tarkov" | "Market";
  entity_type: string;
  entity_id: string;
  correlation_id: string | null;
  trace_data: Record<string, unknown>;
  created_at: string;
}
```

No need to type every classifier's `trace_data` strictly — the viewer renders them generically (see §Component). Add per-classifier types only if we build classifier-specific renderers later.

### 3. Client fetch functions (`src/lib/api.ts`)

Add two new functions:

```typescript
export function getTracesByCorrelation(correlationId: string) {
  return readJson<ReasoningTrace[]>(
    `/api/traces/correlation/${encodeURIComponent(correlationId)}`
  );
}

export function getTraces(classifier: string, entityId: string) {
  return readJson<ReasoningTrace[]>(
    `/api/traces/${encodeURIComponent(classifier)}/${encodeURIComponent(entityId)}`
  );
}
```

### 4. Trace drawer/panel component (`src/components/trace-drawer.tsx`)

A slide-out drawer (or collapsible panel) that renders a list of reasoning traces for a given entity. This is the core UI element.

**Behavior:**

- Receives a `classifier` + `entityId` (or `correlationId`) as props.
- Fetches traces on open, shows a loading skeleton.
- Renders each trace as a collapsible card with:
  - **Header row**: classifier badge (color-coded), entity type, entity ID, timestamp.
  - **Body**: the `trace_data` object rendered as a structured, readable tree.
- Traces are sorted newest-first.
- The drawer can be dismissed.

**Classifier badge colors** (suggestions, match the product palette):

| Classifier | Color token | Meaning |
|-----------|-------------|---------|
| EEM | `--tt-accent-amber` | Event evaluation |
| NSA | `--tt-accent-red` | Person risk scoring |
| Tarkov | `--tt-accent-blue` | Event extraction |
| Market | `--tt-accent-green` | Market data |

**Trace data rendering strategy:**

For v1, render `trace_data` as a **recursive key-value tree** (like a JSON viewer but with human-friendly formatting). Each key is displayed as a label, values are formatted:
- Numbers: mono font, 2 decimal places for floats.
- Strings: normal text, URLs rendered as links.
- Arrays: bulleted list if short (< 10 items), collapsible if long.
- Nested objects: indented sub-section with a subtle border.
- Booleans: green check / red cross icon.

For v2 (later), build classifier-specific renderers that visualize the data more richly (e.g., a waterfall chart for NSA scoring breakdown, a keyword tag cloud for EEM).

### 5. Integration points — where the drawer opens from

There are three natural places to trigger the trace drawer:

#### A. Article row (expanded detail view)

In `article-row.tsx`, add a **"Pokaż trace"** button in the `tt-art-actions` area (next to "Otwórz źródło" and "Eksportuj raport"). On click:
- Open the trace drawer with `classifier="EEM"` and `entityId={article.id}`.
- If the article has a `correlationId` field, also offer a "Pokaż powiązane trace" that loads all traces by correlation.

This requires the `Article` type to carry an optional `correlationId`. If the backend populates `event_id` on articles, map that to the entity lookup.

#### B. Graph node (entity detail panel)

In `company-graph.tsx`, when a user clicks a graph node (Person or Event), show a **trace icon button** in the node tooltip or detail popover. On click:
- **Person node** → open drawer with `classifier="NSA"` and `entityId={node.entityId}`.
- **Event node** → open drawer with `classifier="Tarkov"` and `entityId={node.entityId}`.
- **Company node** → open drawer with `classifier="Market"` and `entityId={node.entityId}`.

#### C. Main panel header (company-level overview)

In `main-panel.tsx`, add a third tab to the `ToggleGroup`: **"Traces"** alongside "Overview" and "Graph". This view shows a filterable list of all recent traces for the selected company, fetched by correlation ID (the company's entity ID as passed to the pipeline).

### 6. Styling (`globals.css`)

Add styles under the existing `tt-*` naming convention:

- `.tt-trace-drawer` — slide-in panel from the right, 480px wide, full height, backdrop blur.
- `.tt-trace-card` — individual trace card within the drawer.
- `.tt-trace-badge` — classifier badge with color coding.
- `.tt-trace-tree` — recursive key-value tree styles.
- `.tt-trace-key` — label styling (mono, muted).
- `.tt-trace-val` — value styling.
- `.tt-trace-tab` — styles for the Traces tab content in main panel.

Use the existing color tokens (`--tt-risk-*`, `--tt-accent`, etc.) and font variables (`--font-jetbrains-mono` for values, `--font-inter-tight` for labels).

### 7. MSW mock handler (`src/mocks/handlers.ts`)

Add mock handlers so the trace UI can be developed and tested without a running backend:

```typescript
http.get('/api/traces/correlation/:correlationId', ({ params }) => {
  return HttpResponse.json(generateMockTraces(params.correlationId as string));
}),
http.get('/api/traces/:classifier/:entityId', ({ params }) => {
  return HttpResponse.json(
    generateMockTraces(params.entityId as string, params.classifier as string)
  );
}),
```

Add a `generateMockTraces` function in `src/mocks/data.ts` that produces realistic trace objects for each classifier type.

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/app/api/traces/correlation/[correlationId]/route.ts` | **create** | BFF proxy for correlation lookup |
| `src/app/api/traces/[classifier]/[entityId]/route.ts` | **create** | BFF proxy for classifier+entity lookup |
| `src/lib/data.ts` | **edit** | Add `ReasoningTrace` type |
| `src/lib/api.ts` | **edit** | Add `getTracesByCorrelation`, `getTraces` |
| `src/components/trace-drawer.tsx` | **create** | Trace viewer drawer component |
| `src/components/article-row.tsx` | **edit** | Add "Pokaż trace" button |
| `src/components/company-graph.tsx` | **edit** | Add trace button on node click |
| `src/components/main-panel.tsx` | **edit** | Add "Traces" tab + trace list view |
| `src/app/globals.css` | **edit** | Add `.tt-trace-*` styles |
| `src/mocks/handlers.ts` | **edit** | Add trace mock endpoints |
| `src/mocks/data.ts` | **edit** | Add mock trace generator |

---

## Implementation Order

1. **Types + API layer** — `data.ts` types, `api.ts` functions, proxy routes. Fast to do, unblocks everything.
2. **MSW mocks** — so the UI can be developed without `docker compose up`.
3. **Trace drawer component** — the core rendering piece.
4. **Article row integration** — simplest entry point, prove the drawer works end-to-end.
5. **Graph node integration** — add trace buttons to Person/Event/Company nodes.
6. **Main panel Traces tab** — company-level trace overview with filtering.
7. **CSS polish** — animations, responsive, dark mode tokens.

---

## UX Considerations

- **Polish language**: all user-facing labels stay in Polish (matching the existing UI): "Ścieżka decyzyjna", "Klasyfikator", "Encja", "Data", etc.
- **Keyboard**: drawer closes on `Escape`, focus is trapped inside when open.
- **Performance**: traces can be large JSON blobs. Virtualize the tree for traces with > 50 keys. Lazy-load the drawer component with `next/dynamic`.
- **Empty state**: when no traces exist for an entity, show a clear "Brak danych trace" message with an explanation that the pipeline may not have processed this entity yet.
- **Error state**: on fetch failure, show a retry button inside the drawer (same pattern as the graph panel).

---

## Non-Goals (v1)

- Trace **comparison** (diffing two traces side by side).
- Trace **search** (full-text search across trace_data).
- Trace **export** (PDF/CSV of trace data).
- Per-classifier **rich visualizations** (waterfall charts, tag clouds). The generic tree renderer is sufficient for v1.
- **Backend changes** — all endpoints already exist.
