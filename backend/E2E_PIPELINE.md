# E2E Pipeline

End-to-End AML Scoring Pipeline that orchestrates the complete flow from scraping to final scoring.

## What it does

Single `POST /v1/pipeline/run` endpoint triggers the full pipeline:

1. **Trigger** - Accepts keyword/company name, starts background job
2. **Scraping** - Fetches ~30 articles from Scuttle Crab
3. **RKR** - Risk keyword filtering (filters irrelevant articles)
4. **Tarkov** - Entity extraction (firms, events, people, connections)
5. **Gathering** - Post-ingestion missing info lookup (founded_at, NIP, REGON)
6. **Timeline** - Date bucket construction (8 equal time periods)
7. **Scoring** - Runs EEM, TrustWeb, NSA in parallel
8. **Merging** - Weighted sum of all module scores
9. **Persistence** - Saves final timeline to database

## Pipeline phases

```
CREATED → SCRAPING → INGESTING → GATHERING → SCORING → MERGING → COMPLETE
```

Each phase updates the `pipeline_run` record. Failed phases move to `FAILED_<phase>`.

## Key components

### Orchestrator (`pipeline/orchestrator.py`)
- Manages async workflow across all phases
- Tracks progress via `pipeline_run` table
- Handles error states and recovery

### Database tables
- `pipeline_run` - Pipeline execution tracking
- `firm_score_timeline` - EEM timeline scores
- `trustweb_score_timeline` - TrustWeb timeline scores
- `final_score_timeline` - Merged scores per bucket

### Scoring modules (parallel execution)
- **EEM** (Module A) - Event enrichment scoring
- **TrustWeb** (Module C) - Graph-based network scoring
- **NSA** (Module B) - People background checking

## Score merging

### Weighted formula
```
final_score[bucket] = 0.40 × eem_score + 0.35 × trustweb_score + 0.25 × nsa_score
```

### Normalization
- EEM: 0-100 → divide by 100 → 0.0-1.0
- TrustWeb: 0.0-1.0 (already normalized)
- NSA: 0.0-1.0 (already normalized)

## API endpoints

### Trigger pipeline
```bash
POST /v1/pipeline/run
{
  "query": "company name or keyword",
  "article_limit": 30
}
# Returns 202 Accepted with run_id
```

### Check status
```bash
GET /v1/pipeline/{run_id}
# Returns phase, progress counts, final scores
```

## Implementation status

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Trigger | POST /v1/pipeline/run endpoint | Not implemented |
| 2. Scraping | Scuttle Crab article fetching | Not implemented |
| 3. RKR | Risk keyword filtering | Implemented |
| 4. Tarkov | Article processing & extraction | Implemented |
| 5. Gathering | Post-ingestion firm enrichment | Not implemented |
| 6. Timeline | Date bucket construction | Not implemented |
| 7a. EEM | Event enrichment scoring | Partially (single score) |
| 7b. TrustWeb | Graph-based scoring | Partially (single score) |
| 7c. NSA | People background check | Partially (dispatch wired) |
| 7d. Parallel | Run all 3 scoring modules | Not implemented |
| 8. Merging | Weighted sum | Not implemented |
| 9. Persistence | Final timeline to DB | Not implemented |
| 10. Orchestrator | Pipeline state machine | Not implemented |

## Current working flow (within scope)

```
POST /v1/articles (single article JSON)
  → IngestionWorker picks up job
    → RKR filters article
      → Tarkov extracts firms, events, people, connections
        → EEM enriches firms (single aggregate score)
        → [if ENABLE_STAGE3_DISPATCH=true] async dispatch to EventClassifier + NSA
```

## What's needed for full E2E

1. **Trigger endpoint** - `POST /v1/pipeline/run` accepting keyword + article limit
2. **Scraper integration** - Scuttle Crab needs HTTP fetching and keyword search mode
3. **Pipeline run tracking** - `pipeline_run` table with state machine
4. **Completion detection** - Know when all articles processed
5. **Missing info gathering** - Post-ingestion firm enrichment (especially `founded_at`)
6. **Timeline module** - Bucket computation for scoring
7. **`founded_at` column** - Add to firm table
8. **EEM timeline scoring** - Partition events into buckets, score per bucket
9. **TrustWeb timeline scoring** - Date filtering through graph layer
10. **TrustWeb auto-invocation** - Wire into pipeline (currently manual)
11. **NSA service** - Actual service that handles scoring
12. **Parallel scoring** - asyncio.gather for EEM + TrustWeb + NSA
13. **Score merger** - Weighted sum with normalization
14. **Timeline tables** - firm_score_timeline, trustweb_score_timeline, final_score_timeline
15. **Pipeline orchestrator** - Async workflow across all phases

## Usage

```python
from pipeline.orchestrator import PipelineOrchestrator

orchestrator = PipelineOrchestrator(config)
result = await orchestrator.run_pipeline(
    query="company name",
    article_limit=30
)
# result.final_score_timeline, result.run_id
```

## Quick start

```bash
# Run Tarkov API
python -m tarkov.main serve --host 0.0.0.0 --port 8081

# Process single article
python -m tarkov.main process-single --article article.json
```