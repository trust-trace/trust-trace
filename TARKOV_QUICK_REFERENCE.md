# Tarkov Implementation - Quick Reference

## Mission Overview

**Tarkov** is Stage 2 of the AML Scoring Pipeline. It transforms raw articles from Scuttle Crab into structured database records (companies, events, people) that feed the downstream scoring modules.

```
Scuttle Crab (Stage 1) 
    → raw articles (JSONL)
Tarkov (Stage 2)
    → extract companies, events, people
    → persist to PostgreSQL
AML Scoring Pipeline (Stage 3)
    → Event Classifier, NSA, TrustWeb
    → score timeline
```

---

## Three Core Responsibilities

1. **Company Identification & Creation**
   - Find company mentions in article text
   - Match against reference dictionary (from Scuttle Crab)
   - Create new firm records in database if needed
   - Track aliases and identifiers (NIP, REGON, KRS)

2. **Event Extraction**
   - Detect money laundering and fraud events
   - Keyword-based approach (MVP) + optional LLM enhancement
   - Calculate risk level (1-10)
   - Assign confidence score
   - Create event records linked to firms

3. **Person Extraction & Linking**
   - Extract people mentioned in events
   - Identify roles (CEO, Director, Owner, etc.)
   - Link people to companies and events
   - Track confidence in extractions

---

## Implementation Phases (10 Phases, 20 Work Days)

### Phase 1: Foundation (Days 1-2)
- Project structure setup
- Dependencies installation (SQLAlchemy, Pydantic, Click, pytest, etc.)
- Database models (ORM mapping to PostgreSQL schema)
- Configuration management

### Phase 2: Company Matching (Days 3-4)
- Company reference loader (from data/companies.json)
- Keyword-based company matching
- Database repository for firm CRUD
- Unit tests for matching logic

### Phase 3: Event Extraction (Days 5-7)
- AML keyword dictionary
- Keyword-based event detector
- Risk level calculation
- Event repository and database persistence
- Optional LLM-based extraction for enhancement

### Phase 4: Person Extraction (Days 8-9)
- Role keyword detection (CEO, Director, Owner, etc.)
- Name pattern matching
- Person database model and repository
- Linking people to companies and events

### Phase 5: Main Pipeline (Days 10-11)
- Article processor orchestrator
- JSONL reader for input
- End-to-end processing flow
- Error handling and dead letter queue

### Phase 6: Testing (Days 12-13)
- Unit tests (>80% coverage)
- Integration tests with real database
- Test fixtures and sample data
- Error scenario tests

### Phase 7: CLI & Operations (Days 14-15)
- CLI commands (process-articles, process-api, import-companies, stats)
- Makefile for common tasks
- Comprehensive README
- Logging and metrics collection

### Phase 8: Documentation & Deployment (Days 16-17)
- Architecture documentation
- API contract documentation
- Dockerfile and docker-compose setup
- Deployment guide

### Phase 9: Performance & Optimization (Days 18-19)
- Batch processing tuning
- Database query optimization
- Caching strategy
- Horizontal scaling considerations

### Phase 10: Final Review (Day 20)
- Code style and linting
- Type checking with mypy
- Acceptance testing
- Production readiness verification

---

## Project Structure

```
backend/
├── tarkov/
│   ├── main.py (CLI entry point)
│   ├── config.py (env-based configuration)
│   ├── database/ (models, repositories)
│   ├── extraction/ (company_matcher, event_extractor, person_extractor)
│   ├── llm/ (LLM client, prompts)
│   ├── schemas/ (Pydantic models)
│   ├── pipeline/ (article processor)
│   ├── storage/ (article reader)
│   ├── keywords/ (AML keyword dictionary)
│   ├── utils/ (logging, text processing)
│   └── tests/ (unit & integration tests)
├── requirements.txt
├── setup.py
├── Dockerfile
├── Makefile
├── README.md
└── docs/ (architecture, database, API contract)
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11+ | Data processing, LLM integration |
| Database ORM | SQLAlchemy 2.0 | Type-safe database access |
| Database | PostgreSQL | ACID compliance, proven reliability |
| LLM | OpenAI/Anthropic | Event extraction enhancement |
| CLI | Click | User-friendly command interface |
| Validation | Pydantic | Type-safe data schemas |
| Testing | pytest | Comprehensive test suite |
| Logging | structlog | Structured, machine-readable logs |
| Type Checking | mypy | Static type safety |
| Code Format | Black | Consistent code style |

---

## Key Design Patterns

1. **Separation of Concerns**
   - Extraction logic independent of database logic
   - Each module has single responsibility
   - Easy to test and maintain

2. **Repository Pattern**
   - Abstract database access
   - Swappable implementations
   - Cleaner testing with mocks

3. **Confidence Scoring**
   - Track confidence in all extractions
   - Allow filtering and manual review
   - Feed into downstream scoring

4. **Batch Processing**
   - Process articles in batches for performance
   - Batch database commits
   - Configurable batch size

5. **Error Resilience**
   - Dead letter queue for failed articles
   - Comprehensive error logging
   - Transaction rollback on failure

---

## Data Flow

### Input (from Scuttle Crab JSONL)
```json
{
  "source": { "name", "domain", "url", "credibility_score" },
  "article": { "title", "text", "published_at", "scraped_at", "canonical_url", "authors", "language" },
  "metadata": { "section", "tags", "tickers", "companies", "region", "discovery_method" }
}
```

### Processing Steps
1. Read article from JSONL
2. Match companies in article text
3. For each company: extract events
4. For each event: extract people
5. Create database records (event, source, people links)
6. Commit transaction

### Output (to PostgreSQL)
- **firm**: Company records (potentially new)
- **event**: Extracted events with risk levels
- **source**: Article as evidence source for event
- **person**: Extracted people
- **person_event**: Links between people and events

---

## Database Schema Integration

### Tables Populated by Tarkov
- **firm**: Create new company records
- **firm_alias**: Add company name aliases
- **event**: Create event records (type, risk_level, occurred_at)
- **source**: Link articles as evidence to events
- **person**: Extract people involved (NEW TABLE)
- **person_event**: Links between people and events (NEW TABLE)

### Database Constraints & Relationships
- event → firm: Many-to-one (multiple events per company)
- source → event: Many-to-one (multiple sources per event)
- person_event → event, person: Many-to-many linking

### Indexes to Add
```sql
CREATE INDEX idx_event_firm_type ON event(firm_id, event_type);
CREATE INDEX idx_source_event_url ON source(event_id, url);
CREATE INDEX idx_person_event_role ON person_event(event_id, role);
```

---

## CLI Commands

```bash
# Process batch of articles
python -m tarkov.main process-articles --input-source jsonl --input-path articles.jsonl

# Process from API stream
python -m tarkov.main process-api --api-endpoint http://localhost:8000/articles

# Import company reference
python -m tarkov.main import-companies --file data/companies.json

# Show statistics
python -m tarkov.main stats

# Validate article schema
python -m tarkov.main validate-schema --file sample_article.json

# Run database migrations
python -m tarkov.main migrate
```

---

## Configuration & Environment

### Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trust_trace

# LLM (optional, for enhanced extraction)
LLM_PROVIDER=openai  # or anthropic
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# File paths
ARTICLE_INPUT_SOURCE=jsonl
ARTICLE_INPUT_PATH=articles.jsonl
KEYWORDS_FILE_PATH=data/aml_keywords.json
COMPANY_REFERENCE_PATH=data/companies.json

# Logging
LOG_LEVEL=INFO
LOG_OUTPUT=console  # or file, loki
```

---

## Key Algorithms

### Company Matching (Keyword-Based)
1. Load company reference dictionary (ticker, aliases)
2. Split article text into words
3. For each word, check against company tickers/aliases
4. Prefer exact matches over substring matches
5. Return list of matched companies with confidence

### Event Extraction (Keyword-Based)
1. Load AML keyword dictionary (organized by event type)
2. Split article into sentences
3. For each sentence, check for keyword matches
4. Group sentences by event type
5. Calculate risk level based on event type and keywords
6. Generate event summary

### Person Extraction (Pattern-Based)
1. Define role keywords (CEO, Director, CFO, etc.)
2. Search for role keywords in article
3. Look for capitalized words before/after role keywords
4. Extract name and role
5. Return list of extracted people with confidence

---

## Error Handling Strategy

### Processing Errors
- **Article parsing error**: Log, write to dead letter queue, continue
- **Company matching failure**: Skip to next article if no firms found
- **Event extraction failure**: Log error, continue (event optional)
- **Person extraction failure**: Log error, continue (person optional)
- **Database constraint violation**: Rollback, log, write to dead letter queue

### Dead Letter Queue
- File: `dead_letters.jsonl`
- Format: Original article + error details + timestamp
- Manual review for investigation

### Resilience
- Transaction rollback on any error
- Idempotent operations (safe to retry)
- Comprehensive logging for debugging

---

## Testing Strategy

### Unit Tests
- Company matching (exact match, substring, case-insensitive)
- Event extraction (keyword detection, risk calculation)
- Person extraction (role detection, name patterns)
- Database repository operations
- Coverage target: >80%

### Integration Tests
- Full pipeline: article → firms → events → people
- Database operations: create, read, verify relationships
- Error scenarios: missing fields, invalid data
- Duplicate handling

### Test Fixtures
- Sample articles (realistic, diverse)
- Sample companies (reference dictionary)
- Sample events (fraud, money laundering, etc.)
- Mock LLM responses

---

## Performance Targets

- **Processing speed**: <1 second per article
- **Throughput**: 100+ articles/minute
- **Memory usage**: <500MB for typical batch
- **Database queries**: <100ms per operation
- **Uptime**: >99%

### Optimization Techniques
- Batch processing (100-1000 articles per batch)
- Database batch inserts
- Lazy loading of company reference
- Connection pooling (SQLAlchemy)
- Query result caching

---

## Deployment

### Docker Setup
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY tarkov/ ./tarkov/
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "tarkov.main", "process-articles"]
```

### Docker Compose
```yaml
services:
  tarkov:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/trust_trace
      LLM_PROVIDER: openai
      LOG_LEVEL: INFO
    depends_on:
      - postgres
    volumes:
      - ./articles.jsonl:/app/articles.jsonl
```

### Production Checklist
- [ ] All tests passing (>80% coverage)
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Logging configured
- [ ] Error handling tested
- [ ] Performance baseline established
- [ ] Documentation complete
- [ ] Docker image built and tested

---

## Success Metrics

1. **Extraction Accuracy**: >85% precision on event extraction
2. **Company Matching**: >90% recall on reference dictionary companies
3. **Processing Speed**: <1 second/article average
4. **Data Quality**: <1% duplicate events
5. **System Reliability**: >99% uptime
6. **Test Coverage**: >80% code coverage
7. **Documentation**: 100% of APIs documented

---

## Downstream Integration

### Input to Scuttle Crab
- Receives articles from Scuttle Crab's output (JSONL)
- Uses company reference from Scuttle Crab (data/companies.json)

### Output to AML Scoring Pipeline (Stage 3)
- Populated **firm** table: Companies with events
- Populated **event** table: AML-related events with risk levels
- Populated **person** table: Key people linked to companies

### Stage 3 Consumption
1. **Event Classifier**: Reads event table, analyzes impact
2. **NSA (Name Scoring Adjudicator)**: Reads person table, background checks
3. **TrustWeb**: Analyzes relationships between firms via events

---

## Document References

- **Full Plan**: `/TARKOV_IMPLEMENTATION_PLAN.md` (47KB, 10 phases, 20 days)
- **AML Scoring Pipeline**: `/AML_SCORING_PIPELINE.md`
- **Scuttle Crab Plan**: `/rust/SCUTTLE_CRAB.md`
- **Database Schema**: `/db/migrations/001_initial_schema.sql`

---

**Status**: ✅ Implementation Plan Complete  
**Created**: 2026-04-27  
**Ready for**: Phase 1 Foundation Setup  
**Estimated Timeline**: 20 work days (4 weeks)
