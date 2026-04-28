# Tarkov

Stage 2 extraction pipeline for Trust Trace. Receives articles from Scuttle Crab, extracts entities, and stores them in the database.

## What it does

1. **Article Ingestion** - HTTP API (`POST /v1/articles`) receives normalized articles from Stage 1
2. **Company Matching** - Matches company names to existing firm records or creates new ones
3. **Entity Extraction** - Extracts AML/fraud events, people, and connections from article text
4. **Data Persistence** - Saves all extracted data to PostgreSQL via SQLAlchemy
5. **Event Dispatch** - Emits `article.parsed` events for Stage 3 scoring modules

## Key components

- `extraction/` - Entity extractors (events, people, connections, companies)
- `database/` - SQLAlchemy models and repositories
- `llm/` - LLM client for entity enrichment
- `utils/` - Helper utilities (logging, text processing)

## Quick start

```bash
# API server
python -m tarkov.main serve --host 0.0.0.0 --port 8081

# Process articles from file
python -m tarkov.main process-articles --input-source jsonl --input-path articles.jsonl
```