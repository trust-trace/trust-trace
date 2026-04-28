# EEM

Event Enrichment Module - Module A of AML Scoring Pipeline. Enriches events with LLM and computes trust scores.

## What it does

1. **Event Fetching** - Retrieves all `event_category = 'classical'` events for a firm from PostgreSQL
2. **LLM Enrichment** - Sends each event through OpenRouter LLM to enrich with display fields
3. **Score Calculation** - Computes a single 0-100 trust score mathematically from per-event impacts
4. **Data Persistence** - Saves enriched fields to `event_enrichment` table, updates `firm_score`

## Public API

```python
from eem import enrich_firm

score = enrich_firm(firm_id=123)
# Returns float in range [0.0, 100.0] - higher = cleaner
```

## Key components

- `database/` - Session, models, repositories
- `llm/` - OpenRouter client
- `config.py` - Environment configuration

## Score interpretation

- 100 = Highest trust (no risk events found)
- 0 = Lowest trust (severe risk events detected)