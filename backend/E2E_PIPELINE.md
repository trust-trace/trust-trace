# E2E Pipeline — Step-by-Step Implementation Checklist

> A single `POST /v1/pipeline/run` endpoint triggers the full AML scoring pipeline:
> scraping → RKR → Tarkov → info gathering → timeline bucketing → EEM + TrustWeb + NSA (parallel) → weighted merge → DB persist.

---

## Legend

- [x] = Implemented and wired
- [ ] = **Not implemented** — details of what's missing follow each unchecked item

---

## Phase 1: Trigger — POST Endpoint

A new REST endpoint accepts a keyword or company name and kicks off the full pipeline as a background job.

### 1.1 `POST /v1/pipeline/run` endpoint

- [ ] **Not implemented.** The only existing endpoint is `POST /v1/articles` which accepts a single pre-scraped article payload and enqueues it for the ingestion worker. There is no endpoint that accepts a keyword/company name and orchestrates the full pipeline.

**What's missing:**
- A new FastAPI route `POST /v1/pipeline/run` with request body `{ "query": "<keyword or company name>", "article_limit": 30 }`
- A new `pipeline_run` database table to track the overall pipeline status (id, query, status, phase, article_target, articles_scraped, articles_processed, firm_ids, final_scores, created_at, completed_at)
- The endpoint should return `202 Accepted` with a `run_id` immediately and execute the pipeline asynchronously

### 1.2 `GET /v1/pipeline/{run_id}` status endpoint

- [ ] **Not implemented.**

**What's missing:**
- A polling endpoint that returns the current pipeline phase, progress counts, and final scores when complete

---

## Phase 2: Scraping — Scuttle Crab

The scraper receives the keyword/company name and fetches ~30 relevant articles from the web.

### 2.1 Scuttle Crab accepts a keyword and scrapes articles

- [ ] **Not implemented.** Scuttle Crab (`rust/scuttle_crab/`) is a Rust crate with CLI scaffolding, payload contract, JSONL outbox, and URL dedup — but **no HTTP fetching, no HTML extraction, no feed discovery, and no end-to-end crawl pipeline** exist yet. The README explicitly lists these as "not implemented yet."

**What's missing:**
- HTTP fetching with retries and timeouts
- RSS/Atom feed parsing or curated page discovery
- HTML extraction into the article payload contract
- A keyword/company-name-driven search mode (e.g., Google News RSS, Bing News API, or curated source search)
- An HTTP API or CLI mode that the Python backend can invoke to request N articles for a given query
- Delivery of scraped articles to the backend (either via HTTP POST to `/v1/articles` or JSONL file handoff)

### 2.2 Backend knows the target article count and tracks progress

- [ ] **Not implemented.** The current `ingestion_job` table tracks individual articles but there is no concept of a "pipeline run" that knows it expects ~30 articles and can determine when all have arrived.

**What's missing:**
- A `pipeline_run` record that stores `article_target` (e.g., 30) and `articles_received` counter
- Logic for Scuttle Crab to tag each article with the `run_id` so the backend can group them
- A completion check: "have all expected articles been received and processed?"

### 2.3 Articles flow into the backend

- [x] **Implemented.** `POST /v1/articles` receives JSON article payloads and enqueues them as `ingestion_job` rows. The `IngestionWorker` background thread polls for due jobs.

---

## Phase 3: RKR — Risk Keyword Regex Filtering

Each article passes through the RKR module to determine relevance before full processing.

### 3.1 RKR filters articles by risk keywords

- [x] **Implemented.** `IngestionWorker._process_job()` runs `RkrArticleProcessor.process_article()` on every incoming article. Articles that don't pass the threshold are marked `skipped`. RKR scores are persisted to the `rkr_scoring` table.

### 3.2 RKR results are persisted

- [x] **Implemented.** `RkrScore` rows are written with `risk_score`, `passed_threshold`, `categories_hit`, and `matched_keywords`.

### 3.3 Only articles passing RKR proceed to Tarkov

- [x] **Implemented.** `if not enriched.rkr.passed_threshold: repo.mark_skipped(job)` gates further processing.

---

## Phase 4: Tarkov — Article Processing & Entity Extraction

Articles that pass RKR are processed by the Tarkov `ArticleProcessor` to extract firms, events, people, and connections.

### 4.1 Article summary generation (LLM)

- [x] **Implemented.** `SummaryGenerator.generate_article_summary()` called in `ArticleProcessor.process_article()`.

### 4.2 Company matching (find or create firms)

- [x] **Implemented.** `CompanyMatcher.match_companies()` + `get_or_create_firm()` + `enrich_firm_profile()` in the processor.

### 4.3 Event extraction (keyword-based + LLM)

- [x] **Implemented.** `EventExtractor.extract_events_keyword_based()` in the processor.

### 4.4 People extraction

- [x] **Implemented.** `PersonExtractor.extract_people()` in the processor.

### 4.5 Connection extraction

- [x] **Implemented.** `ConnectionExtractor.extract_connections()` in the processor.

### 4.6 Postgres persistence (events, sources, people, connections)

- [x] **Implemented.** All entities are persisted via their respective repositories during `process_article()`.

### 4.7 Neo4j standalone node creation (Company, Person, Event)

- [x] **Implemented.** Tarkov repositories (`firm_repo`, `event_repo`, `person_repo`, `source_repo`) call `get_neo4j_session()` to MERGE standalone nodes.

### 4.8 EEM runs per firm after article processing

- [x] **Implemented.** `IngestionWorker._run_eem()` calls `eem.enrich_firm(firm_id)` for each matched firm after Tarkov completes.

### 4.9 Stage-3 dispatch (EventClassifier + NSA) wired via shared emitter

- [x] **Implemented.** `stage3_dispatch.py` provides `build_stage3_result_emitter()` which registers `AMLScoringEventHandler` when `ENABLE_STAGE3_DISPATCH=true`. Both the `IngestionWorker` and CLI commands (`process-articles`, `process-single`) use this shared emitter. After Tarkov persists an article, the emitter fires async scoring requests to EventClassifier and NSA (per firm_id) via `asyncio.gather()`.

---

## Phase 5: Post-Ingestion — Tarkov Gathers Missing Info

After **all** articles in a pipeline run have been processed, Tarkov should automatically look up any missing company information (e.g., founding date, country, registration numbers) needed for downstream scoring.

### 5.1 Pipeline-level completion detection

- [ ] **Not implemented.** The current system processes articles individually with no awareness of a pipeline run. There is no mechanism to detect "all 30 articles have been processed" and trigger a post-ingestion phase.

**What's missing:**
- After each article completes, check if `articles_processed == article_target` for the run
- A state machine for the pipeline run: `scraping → ingesting → gathering → scoring → complete`

### 5.2 Automatic missing-info gathering for firms

- [ ] **Not implemented.** `CompanyMatcher.enrich_firm_profile()` does basic enrichment from article text during processing, but there is no dedicated post-processing step that:
  - Queries the LLM or external APIs for `founded_at` (required for timeline bucketing)
  - Fills in missing registration numbers (NIP, REGON, KRS)
  - Validates/corrects country codes
  - Fetches market identifiers (ticker, exchange) if missing

**What's missing:**
- A `FirmEnricher` service that runs after all articles are ingested
- LLM-based or API-based lookup for `founded_at`, registration details, and market identifiers
- The `founded_at` column on the `firm` table (see Phase 6)

---

## Phase 6: Timeline — Date Bucket Construction

Before scoring, divide the firm's lifetime into 8 equal time periods.

### 6.1 `timeline/` shared module with `compute_timeline_buckets()`

- [ ] **Not implemented.** The `TIMELINE_PLAN.md` describes this module in detail, but no `backend/timeline/` directory exists. Zero Python files found.

**What's missing:**
- `backend/timeline/__init__.py`
- `backend/timeline/buckets.py` with `TimelineBucket` dataclass and `compute_timeline_buckets()` function
- Unit tests

### 6.2 `founded_at` column on `firm` table

- [ ] **Not implemented.** The `firm` table has `created_at` (row insertion time) but no business-level `founded_at`.

**What's missing:**
- SQL migration `003_firm_founded_at.sql`: `ALTER TABLE firm ADD COLUMN founded_at DATETIME`
- ORM update: `founded_at: Mapped[datetime | None]` on the `Firm` model
- Backfill logic for existing rows

### 6.3 Bucket computation uses `founded_at` with `created_at` fallback

- [ ] **Not implemented.** No bucket computation exists yet.

---

## Phase 7: Parallel Scoring — EEM, TrustWeb, NSA

After timeline buckets are set, launch all three scoring modules **asynchronously in parallel**. The backend must wait for all three to complete before proceeding.

### 7.1 EEM — Event Enrichment Module (Module A)

#### 7.1.1 EEM enriches events via LLM

- [x] **Implemented.** `eem._pipeline._run()` loads events, calls `_analyze_event()` per event (LLM-based), computes an aggregate score.

#### 7.1.2 EEM produces a single aggregate score

- [x] **Implemented.** `_compute_score()` returns a 0–100 score with risk level, trend, and keywords.

#### 7.1.3 EEM persists results to `firm_score`

- [x] **Implemented.** `_FirmScoreRepo.upsert()` writes to `firm_score`.

#### 7.1.4 EEM produces timeline scores (per-bucket scoring)

- [ ] **Not implemented.** EEM currently produces a single score per firm. The `TIMELINE_PLAN.md` describes partitioning events into buckets and running `_compute_score()` per bucket, but this is not implemented.

**What's missing:**
- Accept `TimelineBucket` list in `_run()`
- Partition events by `occurred_at` into buckets
- Run `_compute_score()` per bucket (cumulative)
- Return `list[EEMTimelineEntry]` instead of `float`
- Persist to `firm_score_timeline` table (not yet created)
- Update `eem/__init__.py` and `eem/main.py`

### 7.2 TrustWeb — Graph-Based Scoring (Module C)

#### 7.2.1 TrustWeb builds Neo4j graph for firm

- [x] **Implemented.** `build_graph_for_firm()` creates/updates Neo4j nodes and edges using LLM-discovered connections.

#### 7.2.2 TrustWeb extracts subgraph and propagates risk

- [x] **Implemented.** `extract_subgraph()` + `compute_trustweb_score()` via propagation and aggregation.

#### 7.2.3 TrustWeb produces a single score (0.0–1.0)

- [x] **Implemented.** `score_firm()` returns a float score and persists to `trustweb_score`.

#### 7.2.4 TrustWeb produces timeline scores (per-bucket scoring)

- [ ] **Not implemented.** TrustWeb currently builds the graph once and computes one score. Per-bucket scoring requires date-filtered subgraph extraction.

**What's missing (detailed in TIMELINE_PLAN.md §5):**
- `occurred_at` on `SubgraphNode`, `event_occurred_at` on `SubgraphEdge`
- Neo4j Cypher updates to store and return dates on Event nodes and CONNECTION edges
- `builder.py` updates to pass `occurred_at` when writing nodes/edges
- `traversal.py` updates to parse dates and add `filter_subgraph_by_cutoff()`
- `_enrich_risk_levels()` needs a `cutoff` parameter for time-filtered reputation queries
- `score_firm()` looping over buckets
- Persistence to `trustweb_score_timeline` table (not yet created)

#### 7.2.5 TrustWeb is invoked from the pipeline (not manually)

- [ ] **Not implemented.** Currently, TrustWeb is a standalone library invoked via `scripts/run_trustweb.py` or imported directly. It is **not wired** into the ingestion worker or any automated pipeline.

**What's missing:**
- The pipeline orchestrator should call `trust_web.score_firm()` after ingestion completes
- TrustWeb should accept a `run_id` and timeline buckets

### 7.3 NSA — Name Scoring Adjudicator (Module B)

#### 7.3.1 NSA dispatch is wired into Tarkov's post-Stage-2 flow

- [x] **Implemented.** `stage3_dispatch.py` builds a `ResultEmitter` that registers `AMLScoringEventHandler`, which dispatches to both EventClassifier and NSA. The `IngestionWorker` and CLI commands (`process-articles`, `process-single`) both use `build_stage3_result_emitter()`. When `ENABLE_STAGE3_DISPATCH=true`, after Tarkov processes an article, it fires `NSAClient.score_company(firm_id, correlation_id)` per matched firm via `asyncio.gather()`.

#### 7.3.2 NSA HTTP client

- [x] **Implemented.** `NSAClient` in `stage3_clients.py` POSTs to `{NSA_URL}/score/company` with `{ firm_id, correlation_id }`.

#### 7.3.3 NSA service (the actual scoring logic)

- [ ] **Not implemented.** The HTTP client exists and dispatch is wired, but **no NSA service** is running on the other end. There is no `nsa/` module in the backend.

**What's missing:**
- `backend/nsa/` module with:
  - A FastAPI app exposing `POST /score/company`
  - Person background check logic (LLM + optional MCP tool integrations)
  - Per-person risk scoring
  - Average score across all people for a firm
  - Persistence of per-person analysis to database
- For MVP: a mock service that returns a plausible score (e.g., random 0.3–0.7 or a fixed 0.5)

#### 7.3.4 NSA returns a numeric score

- [ ] **Not implemented.** Need a mock service that returns `float` in 0.0–1.0 range.

### 7.4 Parallel execution and await-all

- [ ] **Not implemented.** There is no orchestrator that launches EEM, TrustWeb, and NSA in parallel and waits for all three to complete.

**What's missing:**
- An `asyncio.gather()` (or similar) call that runs all three scoring modules concurrently
- Error handling: if one module fails, the others should still complete; partial results are acceptable
- Progress tracking per module in the `pipeline_run` record

---

## Phase 8: Score Merging — Weighted Sum

After all three modules return their scores (per bucket), merge them into a single timeline score.

### 8.1 Weighted sum formula

- [ ] **Not implemented.** No score merging logic exists.

**What's missing:**
- A `score_merger.py` (or similar) that takes per-bucket scores from EEM, TrustWeb, and NSA and computes a weighted average
- Configurable weights, e.g.:
  ```
  final_score[bucket] = w_eem * eem_score[bucket] + w_trustweb * trustweb_score[bucket] + w_nsa * nsa_score[bucket]
  ```
- Default weights (suggested): EEM=0.40, TrustWeb=0.35, NSA=0.25
- Normalization: EEM is 0–100, TrustWeb is 0.0–1.0, NSA is 0.0–1.0 — need to map to a common scale before merging
- The merged score should be per-bucket, producing an 8-element timeline

### 8.2 Score normalization across modules

- [ ] **Not implemented.**

**What's missing:**
- EEM: divide by 100 to get 0.0–1.0
- TrustWeb: already 0.0–1.0
- NSA: already 0.0–1.0
- Or: scale everything to 0–100

---

## Phase 9: Persistence — Final Timeline to Database

### 9.1 `firm_score_timeline` table

- [ ] **Not implemented.** Described in `TIMELINE_PLAN.md` §6.1 but the migration does not exist.

**What's missing:**
- SQL migration creating `firm_score_timeline` with columns: `id`, `firm_id`, `run_id`, `bucket_index`, `bucket_start`, `bucket_end`, `score`, `risk`, `event_count`, `keywords`, `computed_at`

### 9.2 `trustweb_score_timeline` table

- [ ] **Not implemented.** Described in `TIMELINE_PLAN.md` §6.2 but the migration does not exist.

**What's missing:**
- SQL migration creating `trustweb_score_timeline` and `trustweb_run`

### 9.3 `pipeline_run` table (new)

- [ ] **Not implemented.**

**What's missing:**
- SQL migration creating `pipeline_run` table to track the overall pipeline execution

### 9.4 `final_score_timeline` table (new)

- [ ] **Not implemented.**

**What's missing:**
- A table to store the **merged** final scores per bucket per firm per run:
  ```sql
  CREATE TABLE final_score_timeline (
      id              SERIAL PRIMARY KEY,
      firm_id         BIGINT NOT NULL REFERENCES firm(id) ON DELETE CASCADE,
      run_id          UUID NOT NULL,
      bucket_index    SMALLINT NOT NULL,
      bucket_start    TIMESTAMP NOT NULL,
      bucket_end      TIMESTAMP NOT NULL,
      eem_score       DECIMAL(5,2),
      trustweb_score  DECIMAL(4,3),
      nsa_score       DECIMAL(4,3),
      final_score     DECIMAL(4,3) NOT NULL,
      risk_level      VARCHAR(10) NOT NULL,
      computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(run_id, bucket_index)
  );
  ```

### 9.5 Final scores are persisted per bucket

- [ ] **Not implemented.** No persistence layer for merged timeline scores exists.

---

## Phase 10: Pipeline Orchestrator — Glue Code

The orchestrator ties all phases together as a single async workflow.

### 10.1 Pipeline state machine

- [ ] **Not implemented.**

**What's missing:**
- A `PipelineOrchestrator` class (or async function) that manages the pipeline lifecycle:
  ```
  CREATED → SCRAPING → INGESTING → GATHERING → SCORING → MERGING → COMPLETE
  ```
- Each phase transition updates the `pipeline_run` record
- Error states: `FAILED_SCRAPING`, `FAILED_SCORING`, etc.

### 10.2 Scraper invocation

- [ ] **Not implemented.** The orchestrator needs to call Scuttle Crab (via subprocess, HTTP, or message queue) with the query and article limit.

### 10.3 Ingestion monitoring

- [ ] **Not implemented.** The orchestrator needs to wait until all scraped articles have been processed by the ingestion worker.

### 10.4 Post-ingestion enrichment trigger

- [ ] **Not implemented.** After all articles are processed, trigger the firm enrichment step (missing info gathering).

### 10.5 Timeline bucket computation

- [ ] **Not implemented.** After enrichment, compute timeline buckets for each relevant firm.

### 10.6 Parallel scoring dispatch

- [ ] **Not implemented.** Launch EEM, TrustWeb, and NSA concurrently with `asyncio.gather()`.

### 10.7 Score merging and persistence

- [ ] **Not implemented.** After all modules return, compute weighted sums and persist.

---

## Summary

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Trigger | `POST /v1/pipeline/run` endpoint | **Not implemented** |
| 2. Scraping | Scuttle Crab fetches articles by keyword | **Not implemented** (Rust crate is scaffolding only) |
| 3. RKR | Risk keyword filtering | **Implemented** |
| 4. Tarkov | Article processing & entity extraction | **Implemented** |
| 5. Gathering | Post-ingestion missing-info lookup | **Not implemented** |
| 6. Timeline | Date bucket construction | **Not implemented** (`timeline/` module, `founded_at` column) |
| 7a. EEM | Event enrichment scoring | **Partially implemented** (single score works; timeline scoring missing) |
| 7b. TrustWeb | Graph-based scoring | **Partially implemented** (single score works; timeline scoring + auto-invocation missing) |
| 7c. NSA | People background scoring | **Partially implemented** (dispatch wired via stage3_dispatch.py + NSAClient; actual NSA service/module missing) |
| 7d. Parallel exec | Run 7a+7b+7c concurrently, await all | **Not implemented** |
| 8. Merging | Weighted sum across modules | **Not implemented** |
| 9. Persistence | Final timeline scores to DB | **Not implemented** |
| 10. Orchestrator | Pipeline state machine tying all phases | **Not implemented** |

### What's fully working today (end-to-end within its scope):

```
POST /v1/articles (single article JSON)
  → IngestionWorker picks up job
    → RKR filters article
      → Tarkov extracts firms, events, people, connections (Postgres + Neo4j)
        → EEM enriches firms (single aggregate score)
        → [if ENABLE_STAGE3_DISPATCH=true] async dispatch to EventClassifier + NSA (HTTP clients only; services must be running externally)
```

### What's needed for the full E2E pipeline:

1. **Trigger endpoint** — `POST /v1/pipeline/run` with keyword + article limit
2. **Scraper integration** — Scuttle Crab needs HTTP fetching, HTML extraction, and a keyword search mode; backend needs an invocation mechanism
3. **Pipeline run tracking** — `pipeline_run` table + state machine
4. **Completion detection** — Know when all articles for a run are processed
5. **Missing-info gathering** — Post-ingestion firm enrichment (especially `founded_at`)
6. **Timeline module** — `backend/timeline/` with bucket computation
7. **`founded_at` migration** — Add column to `firm` table
8. **EEM timeline scoring** — Partition events into buckets, score per bucket
9. **TrustWeb timeline scoring** — Date threading through graph layer, filter subgraph per bucket
10. **TrustWeb auto-invocation** — Wire into pipeline (currently manual/standalone)
11. **NSA service** — Dispatch is wired and HTTP client exists, but the actual service (or mock) that handles `POST /score/company` is missing
12. **Parallel scoring** — `asyncio.gather()` for EEM + TrustWeb + NSA (NSA dispatch already uses `asyncio.gather` for per-article stage-3, but the pipeline-level "run all 3 modules for all firms and wait" orchestration is missing)
13. **Score merger** — Weighted sum with normalization across different scales
14. **Timeline DB tables** — `firm_score_timeline`, `trustweb_score_timeline`, `final_score_timeline`
15. **Pipeline orchestrator** — Async workflow managing all phases sequentially
