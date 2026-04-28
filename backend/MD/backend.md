# Backend

The backend is the data processing and scoring engine for Trust Trace AML platform. It handles the complete pipeline from article ingestion through to risk scoring.

## Architecture Overview

```
Scuttle Crab (Stage 1) → API → Tarkov (Stage 2) → Pipeline → TrustWeb/EEM/RKR (Stage 3) → Final Score
```

## Key Modules

### `tarkov/` — Stage 2: Extraction Pipeline
- **Purpose**: Article ingestion and entity extraction
- **Functionality**:
  - HTTP API (`POST /v1/articles`) receives normalized articles from Scuttle Crab
  - Matches companies and creates/links firm records
  - Extracts AML/fraud events, people, and connections
  - Persists data to PostgreSQL via SQLAlchemy
  - Emits `article.parsed` events for Stage 3 modules
- **Tech**: Python/FastAPI, PostgreSQL, SQLAlchemy

### `pipeline/` — E2E Orchestration
- **Purpose**: Coordinates the full pipeline lifecycle
- **Phases**: CREATED → SCRAPING → INGESTING → GATHERING → SCORING → MERGING → COMPLETE
- **Manages**: Pipeline runs, scraper adapters, score merging

### `trust_web/` — Graph-Based Risk Scoring (Module C)
- **Purpose**: Network correlation scoring
- **Functionality**:
  - Reads entities from PostgreSQL
  - Creates Neo4j nodes and uses LLM to discover connections
  - Runs iterative risk propagation algorithm
  - Produces trust score (0.0–1.0) with human-readable explanation
- **Tech**: Neo4j, OpenRouter LLM

### `eem/` — Event Enrichment Module (Module A)
- **Purpose**: Event-based trust scoring
- **Functionality**:
  - Fetches classical events for a firm
  - Sends events through LLM for enrichment
  - Computes trust score mathematically from per-event impacts
  - Returns 0–100 score

### `rkr/` — Risk Keyword Recognition
- **Purpose**: Keyword-based risk analysis
- **Functionality**: Scans articles for risk-related keywords and patterns

### `nsa/` — News Sentiment Analysis
- **Purpose**: Analyzes sentiment from news sources

### `timeline/` — Timeline Buckets
- **Purpose**: Temporal grouping of events for visualization

### `reasoning/` — Reasoning Traces
- **Purpose**: Stores and formats reasoning traces from LLM decisions

## Data Flow

1. **Scuttle Crab** sends normalized articles to Tarkov API
2. **Tarkov** extracts entities (companies, people, events) and stores in PostgreSQL
3. **Pipeline Orchestrator** triggers Stage 3 scoring modules
4. **TrustWeb** builds graph, discovers connections, propagates risk
5. **EEM** enriches events, computes event-based scores
6. **Score Merger** combines all scores into final result

## Database

- **PostgreSQL**: Firms, events, persons, sources, connections
- **Neo4j**: Company graph (nodes + edges created by TrustWeb)

## Quick Start

```bash
# Setup
python -m venv .venv
. .venv/Scripts/activate
pip install -r backend/requirements.txt

# Run Tarkov API
python -m tarkov.main serve --host 0.0.0.0 --port 8081

# Run E2E Pipeline
python -c "from pipeline.orchestrator import PipelineOrchestrator; ..."
```