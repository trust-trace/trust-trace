# Tarkov Backend - Run Instructions

## Prerequisites

- Python 3.11+
- PostgreSQL or SQLite (development)
- pip/venv

## Setup (One-Time)

```bash
# From project root
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create `.env` file in `backend/` directory or export environment variables:

```bash
# Database
DATABASE_URL=sqlite+pysqlite:///:memory:
# or PostgreSQL: DATABASE_URL=postgresql://user:pass@localhost/tarkov_db

# Logging
LOG_LEVEL=INFO

# LLM (optional)
LLM_PROVIDER=none  # or "openai" or "anthropic"
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_WEB_SEARCH_ENABLED=false  # set true to enable OpenRouter web search for enrichment

# File paths
ARTICLE_INPUT_SOURCE=jsonl
ARTICLE_INPUT_PATH=articles.jsonl
COMPANY_REFERENCE_PATH=backend/tarkov/data/companies.json
KEYWORDS_FILE_PATH=backend/tarkov/data/aml_keywords.json
DEAD_LETTER_PATH=backend/tarkov/dead_letters.jsonl

# API Server
TARKOV_API_HOST=0.0.0.0
TARKOV_API_PORT=8081

# Stage 3 Dispatch (optional)
ENABLE_STAGE3_DISPATCH=false
EVENT_CLASSIFIER_URL=
NSA_URL=
TRUSTWEB_URL=
```

## Running Tarkov

### Option 1: API Server (Recommended for Stage 1 -> Stage 2 integration)

```bash
python -m tarkov.main serve
```

Server starts at `http://0.0.0.0:8081`

Health check:
```bash
curl http://localhost:8081/health
```

Post an article:
```bash
curl -X POST http://localhost:8081/v1/articles \
  -H "Content-Type: application/json" \
  -d @article_payload.json
```

### Option 2: Batch Processing from JSONL

```bash
python -m tarkov.main process-articles \
  --input-source jsonl \
  --input-path articles.jsonl \
  --batch-size 100
```

### Option 3: Process Single Article

```bash
python -m tarkov.main process-single article.json
```

## Running Tests

```bash
# All tests
pytest backend/tarkov/tests -v

# Specific test file
pytest backend/tarkov/tests/test_api.py -v

# Integration tests only
pytest backend/tarkov/tests/integration/ -v

# Run with coverage
pytest backend/tarkov/tests --cov=tarkov --cov-report=html
```

## Example Article Payload

```json
{
  "source": {
    "name": "Reuters",
    "domain": "reuters.com",
    "url": "https://reuters.com/article/123",
    "credibility_score": 0.9,
    "credibility_label": "high"
  },
  "article": {
    "title": "Company X Faces Fraud Investigation",
    "text": "Acme Corp CEO was investigated for fraud and suspicious transactions...",
    "published_at": "2026-04-27T08:00:00Z",
    "scraped_at": "2026-04-27T09:00:00Z",
    "canonical_url": "https://reuters.com/article/123",
    "authors": ["Jane Reporter"],
    "language": "en"
  },
  "metadata": {
    "section": "business",
    "tags": ["fraud", "investigation"],
    "tickers": ["ACME"],
    "companies": ["Acme Corp"],
    "region": "US",
    "discovery_method": "rss",
    "http_status": 200
  }
}
```

## Troubleshooting

### Database issues
- Check `DATABASE_URL` is valid and service is running
- For SQLite, ensure directory exists for database file
- Migrations: tables auto-create on first run

### Article not processed
- Check logs for company match failures (requires `companies.json` entries)
- Verify payload schema matches `backend/tarkov/schemas/article.py`

### LLM features not working
- Ensure `LLM_PROVIDER` is set and `LLM_API_KEY` is valid
- Fallback to keyword extraction always works

### Stage 3 dispatch not triggering
- Set `ENABLE_STAGE3_DISPATCH=true`
- Provide valid `EVENT_CLASSIFIER_URL`, `NSA_URL`, `TRUSTWEB_URL`
- Check logs for async task errors (non-blocking, won't fail ingestion)

## Development

### Format code
```bash
black backend/tarkov
```

### Check types
```bash
mypy backend/tarkov
```

### Quick syntax check
```bash
python -m py_compile backend/tarkov/**/*.py
```

## Logs

Logs written to console (configured via `LOG_LEVEL`).

For file logging, modify `backend/tarkov/utils/logger.py`.

Dead letters (processing failures) written to `DEAD_LETTER_PATH` (default: `backend/tarkov/dead_letters.jsonl`).

## Integration with Scuttle Crab

See `SCUTTLE_TO_TARKOV_IMPLEMENTATION_PLAN.md` for end-to-end setup.

Quick test:
```bash
# Terminal 1: Start Tarkov API
python -m tarkov.main serve

# Terminal 2: Send test payload
curl -X POST http://localhost:8081/v1/articles \
  -H "Content-Type: application/json" \
  -d @backend/tarkov/tests/fixtures/sample_articles.json
```

## Database Schema

Auto-created on first run. Models in `backend/tarkov/database/models.py`:
- `firm`: Companies
- `firm_alias`: Company name/ticker aliases
- `event`: AML/fraud events
- `source`: Evidence (articles, summaries, extracts)
- `person`: People associated with events
- `person_event`: Person-event links
- `connection_entity`: Relationships (shared directors, business links, etc.)
- `article_metadata`: Ingestion metadata and processing status
