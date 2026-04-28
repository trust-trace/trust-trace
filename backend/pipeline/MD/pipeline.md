# Pipeline

E2E pipeline orchestrator that manages the complete flow from scraping to final scoring.

## What it does

Coordinates the full pipeline lifecycle through phases:

1. **CREATED** - Pipeline run created
2. **SCRAPING** - Fetches articles from web sources
3. **INGESTING** - Sends articles to Tarkov for extraction
4. **GATHERING** - Collects entities from database
5. **SCORING** - Runs Stage 3 scoring modules (TrustWeb, EEM, RKR)
6. **MERGING** - Combines all scores into final result
7. **COMPLETE** - Pipeline finished successfully

## Key components

- `orchestrator.py` - Main async orchestrator
- `scraper_adapter.py` - Adapter for different scraper backends
- `score_merger.py` - Combines scores from multiple modules
- `firm_enricher.py` - Firm data enrichment
- `models.py` - Pipeline data models

## Usage

```python
from pipeline.orchestrator import PipelineOrchestrator

orchestrator = PipelineOrchestrator(config)
result = await orchestrator.run_pipeline(query="company name")
```