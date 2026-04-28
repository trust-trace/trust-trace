# Handoff

## Goal

Wire NSA into Tarkov's post-Stage-2 pipeline so it runs after Tarkov finishes persistence, using the same async stage-3 dispatch path as the ingestion worker.

## What Changed

- Added `backend/tarkov/pipeline/stage3_dispatch.py` with `build_stage3_result_emitter()`.
- Updated `backend/tarkov/main.py` so `process-articles` and `process-single` both use the shared stage-3 emitter.
- Updated `backend/tarkov/pipeline/ingestion_worker.py` to use the same shared emitter.
- Added a test in `backend/tarkov/tests/test_pipeline.py` to confirm NSA dispatch registration when stage 3 is enabled.

## Current Behavior

- When `ENABLE_STAGE3_DISPATCH=true`, Tarkov emits parsed results to the async stage-3 handler after Stage 2 persistence.
- NSA dispatch is already implemented in `AMLScoringEventHandler`; the missing piece was making the direct CLI pipeline use the same wiring as the worker.

## Verification

- `python -m pytest backend/tarkov/tests/test_pipeline.py -q`
- `python -m pytest backend/tarkov/tests/test_api.py -q`

## Worktree Notes

- `git add .` has already been run.
- The worktree also contains pre-existing staged changes in:
  - `backend/tarkov/llm/client.py`
  - `backend/tarkov/llm/prompts.py`
  - `backend/tarkov/tests/test_llm_client.py`
- I did not modify those LLM files as part of the NSA pipeline change.

## Next Steps

- Review the staged LLM-related files before committing.
- If needed, run the broader Tarkov test suite before finalizing a commit.
