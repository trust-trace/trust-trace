# Scuttle Crab -> Tarkov Integration Implementation Plan

## Purpose

Define and implement a single reliable contract where `scuttle_crab` sends one `POST /v1/articles` per article and `tarkov` performs all downstream Stage 2 responsibilities (persist, extract, emit Stage 3 dispatch events).

---

## Level 1 - High-Level Architecture And Outcomes

### 1) Target System Behavior

- Stage 1 (`rust/scuttle_crab`) is only responsible for discovery/fetch/extraction/normalization/dedup and HTTP delivery to Tarkov.
- Stage 2 (`backend/tarkov`) is responsible for validation, persistence, extraction, enrichment, dead-letter handling, and optional Stage 3 fan-out.
- Integration boundary is strict: one schema, one endpoint (`POST /v1/articles`), one idempotency strategy.

### 2) High-Level Product Outcome

- `scuttle_crab` can run continuously and deliver article payloads directly to Tarkov.
- Tarkov can process each payload safely, avoid duplicate processing, persist complete extraction output, and expose processing status.
- If Stage 3 dispatch is enabled, Tarkov fans out parsed events to Event Classifier / NSA / TrustWeb without blocking ingestion reliability.

### 3) Top-Level Non-Functional Requirements

- Reliability: retry-safe delivery and idempotent ingestion.
- Observability: correlation IDs, structured logs, processing counters, and health checks.
- Recoverability: dead-letter records for malformed or failed payloads.
- Backward compatibility: support current Scuttle payload shape during migration.

---

## Level 2 - Mid-Level Workstreams

## Workstream A - Integration Contract Hardening

### Goals

- Freeze a versioned payload contract between Scuttle and Tarkov.
- Ensure all required fields are validated consistently.

### Scope

- Define contract version header (`X-Payload-Version: 1`) and optional `X-Correlation-Id`.
- Keep body shape as:
  - `source`
  - `article`
  - `metadata`
- Add idempotency key strategy: prefer `article.canonical_url` else `source.url` + `article.title` hash.

### Deliverables

- Contract markdown in Tarkov docs.
- Pydantic schema updates and validation tests.
- Scuttle sender adapter producing compliant requests.

## Workstream B - Tarkov Ingestion Reliability

### Goals

- Make Tarkov the single processing authority after POST.
- Prevent duplicate processing and partial writes.

### Scope

- Persist ingestion metadata (`article_metadata`) for every accepted request.
- Enforce idempotency at DB level (unique idempotency key).
- Return deterministic API statuses:
  - `processed`
  - `duplicate`
  - `skipped`
  - `failed`
- Keep dead-letter writes for processing exceptions.

### Deliverables

- `ArticleMetadata` repository/service implementation.
- Ingestion idempotency checks in API/processor path.
- API tests for duplicate and retry scenarios.

## Workstream C - Extraction/Persistence Completion

### Goals

- Ensure Tarkov fully handles extraction and storage for events, people, connections, sources.

### Scope

- Continue keyword extraction baseline, keep optional LLM fallback.
- Persist source evidence consistently for each extracted event/person/connection as needed.
- Normalize and store processing summary + risk rollup.

### Deliverables

- Repository coverage for all persisted entities.
- Integration tests asserting full DB side effects.

## Workstream D - Stage 3 Dispatch Decoupling

### Goals

- Keep Stage 3 fan-out optional and non-blocking for ingestion success.

### Scope

- Emit `article.parsed` regardless of dispatch enablement.
- If dispatch enabled, run async calls with timeout and error capture.
- Do not fail article ingestion on downstream scoring endpoint failures.

### Deliverables

- Hardened async handler behavior and error logging.
- Tests for dispatch enabled/disabled/failure modes.

## Workstream E - Scuttle Delivery Path

### Goals

- Add production-ready sender from Scuttle outbox/pipeline to Tarkov endpoint.

### Scope

- Add `deliver` module in Scuttle:
  - POST JSON payload to Tarkov.
  - Retry with exponential backoff on transient failures.
  - Respect HTTP status semantics (`2xx` success, `409 duplicate`, `4xx` permanent reject, `5xx` retry).
- Config knobs:
  - `TARKOV_BASE_URL`
  - `TARKOV_INGEST_PATH` (default `/v1/articles`)
  - timeout/retries/max in-flight

### Deliverables

- Scuttle HTTP delivery implementation.
- End-to-end local integration runbook and smoke test.

---

## Level 3 - Low-Level Implementation Plan (Near Implementation)

## Phase 0 - Baseline And Safety (Day 0-1)

1. Add this plan and create implementation checklist issues.
2. Add integration feature flags/env defaults in both services.
3. Define exact response contract for `POST /v1/articles` including duplicate semantics.

Definition of Done:

- Contract and response examples committed.
- Team agreement on idempotency key algorithm.

## Phase 1 - Tarkov Contract + Idempotency (Day 1-3)

### Code Targets

- `backend/tarkov/schemas/article.py`
- `backend/tarkov/api.py`
- `backend/tarkov/pipeline/processor.py`
- `backend/tarkov/database/models.py`
- new: `backend/tarkov/database/repositories/article_metadata_repo.py`

### Tasks

1. Extend request handling to read headers:
   - `X-Correlation-Id` (optional, generate if missing)
   - `X-Payload-Version` (default to `1` if absent)
2. Implement idempotency key computation function:
   - primary: normalized `article.canonical_url`
   - fallback: normalized `source.url` + normalized `article.title`
3. Add unique DB constraint/index for idempotency key in `article_metadata`.
4. On duplicate key, return `200/409` agreed status with body `{ "status": "duplicate", ... }`.
5. Persist `article_metadata` on every accepted payload with correlation ID and processing timestamps.

### Tests

- Add API tests:
  - first POST -> `processed`
  - same POST replay -> `duplicate`
  - malformed payload -> `422`

Definition of Done:

- Replay-safe ingestion proven by tests.
- Metadata table populated per accepted request.

## Phase 2 - Tarkov “Handles The Rest” Completion (Day 3-5)

### Code Targets

- `backend/tarkov/pipeline/processor.py`
- `backend/tarkov/database/repositories/*.py`
- `backend/tarkov/pipeline/result_emitter.py`
- `backend/tarkov/pipeline/event_handlers.py`

### Tasks

1. Ensure full transaction boundaries:
   - persist firms/events/people/links/sources/connections
   - persist metadata updates (`processed_at`, `companies_found`, status)
2. Ensure dead-letter write includes correlation ID and idempotency key.
3. Make Stage 3 dispatch strictly non-blocking:
   - log and capture dispatch failures
   - never rollback successful Stage 2 persistence because Stage 3 failed
4. Add deterministic response payload fields (`article_id`, counts, status).

### Tests

- Integration test with sample article asserts:
  - firm/event/person/source/connection created
  - metadata updated
  - dead-letter not written on success
- Dispatch-failure test asserts ingestion still succeeds.

Definition of Done:

- Tarkov can ingest a valid payload and complete Stage 2 side effects independently.

## Phase 3 - Scuttle Direct POST Delivery (Day 5-8)

### Code Targets

- `rust/scuttle_crab/src/crawler/` (add sender module)
- `rust/scuttle_crab/src/config.rs`
- `rust/scuttle_crab/src/lib.rs` / command path

### Tasks

1. Add `reqwest::Client`-based sender for Tarkov ingestion.
2. Add sender config values (base URL, timeout, retries, concurrency).
3. Send one payload per article with headers:
   - `Content-Type: application/json`
   - `X-Payload-Version: 1`
   - `X-Correlation-Id: <uuid>`
4. Implement retry policy:
   - retry on network errors and `5xx`
   - no retry on `4xx` except optional retry on `429` with backoff
   - treat `duplicate` response as success terminal state
5. Persist local delivery results (success/failure metrics) in logs.

### Tests

- Unit test payload serialization compatibility with Tarkov schema.
- Integration test against local Tarkov test server:
  - valid payload -> success
  - duplicate payload -> duplicate success path

Definition of Done:

- Scuttle can run and reliably deliver article payloads to Tarkov endpoint.

## Phase 4 - End-to-End Hardening (Day 8-10)

### Tasks

1. Run E2E smoke:
   - Scuttle emits sample payloads -> Tarkov persists records.
2. Add operational runbook:
   - env vars
   - startup order
   - health checks
   - failure triage steps
3. Add metrics/log fields:
   - ingestion rate
   - duplicate rate
   - extraction failure rate
   - dispatch failure rate

Definition of Done:

- Repeatable local E2E run documented.
- Production-readiness checklist completed.

---

## Precise Sequencing (Execution Order)

1. Ship Tarkov idempotency + metadata persistence first.
2. Ship Tarkov non-blocking Stage 3 dispatch behavior second.
3. Ship Scuttle HTTP sender third.
4. Validate with E2E tests and runbook last.

This order ensures Scuttle can start posting only after Tarkov is safe for retries and duplicate deliveries.

---

## Acceptance Criteria (System-Level)

- A Scuttle-produced article payload can be POSTed to Tarkov without manual transforms.
- Replaying the same payload does not create duplicate Stage 2 entities.
- Tarkov performs company matching, event/person/connection extraction, persistence, and event emission automatically.
- Stage 3 endpoint failures do not fail ingestion of valid articles.
- Correlation ID can trace one payload from ingress to persistence and dispatch logs.

---

## Risks And Mitigations

- Idempotency collisions from weak fallback key -> use canonical URL first and include title hash fallback.
- Dispatch tasks dropped under event-loop edge cases -> add explicit async execution strategy and tests.
- Schema drift between Rust and Python models -> add contract tests using shared payload fixtures.
- Silent extraction degradation -> add integration assertions on minimum extracted artifact counts.

---

## Immediate Next Actions

1. Implement Phase 1 in Tarkov (`idempotency + article_metadata repo + tests`).
2. Implement Phase 2 in Tarkov (`transaction/state updates + dispatch isolation`).
3. Implement Phase 3 in Scuttle (`HTTP sender + retry policy + integration test`).
