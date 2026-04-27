# Tarkov

Tarkov is the Stage 2 extraction pipeline for Trust Trace.

## What it does

- Reads raw articles from JSONL or API sources
- Exposes HTTP ingestion endpoint for Scuttle Crab (`POST /v1/articles`)
- Matches companies and creates/links firm records
- Extracts AML/fraud events, people, and connections
- Persists extracted data to SQL database via SQLAlchemy
- Emits `article.parsed` events for Stage 3 modules

## Stage Integration

- Stage 1 (`rust/scuttle_crab`) sends normalized article payloads to Tarkov API
- Stage 2 (this service) processes payloads and persists companies/events/people/sources
- Stage 3 dispatch can be enabled via `ENABLE_STAGE3_DISPATCH=true` to call Event Classifier, NSA, and TrustWeb HTTP endpoints

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r backend/requirements.txt
```

Run pipeline:

```bash
python -m tarkov.main process-articles --input-source jsonl --input-path articles.jsonl
```

Run API server for Stage 1 -> Stage 2 ingestion:

```bash
python -m tarkov.main serve --host 0.0.0.0 --port 8081
```

Send article from Scuttle Crab output shape:

```bash
curl -X POST http://localhost:8081/v1/articles \
  -H "Content-Type: application/json" \
  -d @article_payload.json
```

Run tests:

```bash
pytest backend/tarkov/tests -q
```
