# Stage 2 -> Stage 3 Glue Plan

## Scope

This document covers only the glue between the currently implemented Tarkov backend and the next pipeline stages. No extractor logic, scoring logic, or frontend work is included.

## Goal

Move one article through Tarkov and into the scoring pipeline with a clean, linear handoff and enough logging to debug anything unusual.

## Step-by-step implementation order

### 1) Define the Stage 2 exit object
- Tarkov must emit one canonical handoff record after persistence succeeds.
- The handoff must include company identity, article identity, correlation ID, extracted entity IDs, and source references.
- This record becomes the only input to Stage 3.

### 2) Persist the handoff before dispatch
- Stage 3 dispatch must happen after Tarkov commits its database writes.
- The dispatch target should be derived from a persisted job row, not from in-memory article state.
- Dispatch must be idempotent.

### 3) Standardize module request envelopes
- Event Classifier, NSA, and TrustWeb must all receive a shared envelope with:
  - `job_id`
  - `correlation_id`
  - `company_id`
  - `schema_version`
  - `as_of`
- Each module then receives its own payload slice.

### 4) Make module dispatch parallel
- Start all eligible module calls together.
- Keep the calls independent so they do not block each other.
- If something goes wrong, log it clearly for debugging and keep the pipeline moving.

### 5) Aggregate module outputs into one scoring package
- Store raw module scores separately from the combined score.
- Keep the weighting formula versioned.
- Preserve evidence references alongside the final score.

### 6) Generate a score timeline
- The final output is a series of dated snapshots, not a single value.
- Timeline generation uses company age as the snapshot count driver.
- Each snapshot should preserve module contributions and the combined score.

### 7) Persist graph glue for TrustWeb
- Tarkov’s connection data is the source of truth for graph edges.
- Normalize edge type, direction, and intensity before scoring.
- Limit traversal to depth 2.

### 8) Persist module analysis text
- Event analysis attaches to event records.
- Person analysis attaches to person records.
- Graph analysis attaches to graph/edge records.

### 9) Add logging and visibility
- Log every module request and response with correlation metadata.
- Log unexpected exceptions with enough context to debug quickly.
- Keep the main flow focused on the successful path.

## Recommended file touchpoints

- `backend/tarkov/api.py`
- `backend/tarkov/pipeline/processor.py`
- `backend/tarkov/pipeline/result_emitter.py`
- `backend/tarkov/pipeline/event_handlers.py`
- `backend/tarkov/pipeline/stage3_clients.py`
- `backend/tarkov/database/models.py`
- `backend/tarkov/database/repositories/article_metadata_repo.py`

## Success criteria

- Tarkov can finish Stage 2 and hand off a complete, replay-safe job.
- Stage 3 can consume the handoff without needing to inspect raw ingest state.
- Any unexpected issue is visible in logs with the right correlation data.
