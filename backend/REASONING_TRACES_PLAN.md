# Reasoning Traces

Module for capturing and storing decision-making logic from all classifiers. Provides transparency, auditability, and debugging capabilities.

## What it does

1. **Trace Collection** - Captures LLM reasoning decisions at each classifier
2. **Storage** - Persists traces to database for audit
3. **Formatting** - Formats traces for frontend display
4. **Query API** - Allows fetching traces by classifier, entity, or correlation

## Supported classifiers

- **EEM** - Event enrichment decisions (sentiment, impact, keywords)
- **NSA** - Person scoring decisions (evidence weights, aggregations)
- **RKR** - Keyword matching decisions (matches, scores, thresholds)
- **Tarkov** - Event extraction decisions (confidence, risk levels)
- **Market** - Ticker search and fetch decisions

## Key components

### Collectors
- `collectors/eem_collector.py` - EEM trace collector
- `collectors/nsa_collector.py` - NSA trace collector
- `collectors/rkr_collector.py` - RKR trace collector
- `collectors/tarkov_collector.py` - Tarkov trace collector
- `collectors/market_collector.py` - Market trace collector

### Storage
- `storage.py` - Database persistence
- `session.py` - Trace session management

### Formatters
- `formatters.py` - Human-readable output

## Trace data model

### EEM Reasoning Trace
```python
{
  "model_used": "llm" | "deterministic",
  "fallback_reason": str | None,
  "sentiment_calculation": {...},
  "impact_scoring": {...},
  "source_tier_logic": {...},
  "keyword_extraction": {...}
}
```

### RKR Reasoning Trace
```python
{
  "language_detected": str,
  "keyword_matches": [...],
  "score_calculation": {...},
  "categories_aggregated": {...},
  "threshold_decision": {...}
}
```

## Database schema

```sql
CREATE TABLE reasoning_traces (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  classifier_name VARCHAR(50) NOT NULL,
  entity_type VARCHAR(100) NOT NULL,
  entity_id VARCHAR(255) NOT NULL,
  correlation_id VARCHAR(255),
  trace_data JSONB NOT NULL,
  created_at DATETIME DEFAULT NOW(),
  INDEX (classifier_name, created_at),
  INDEX (correlation_id),
  INDEX (entity_id)
);
```

## API usage

### Include traces in responses
```bash
GET /api/v1/enrichment/{event_id}?include_reasoning=true
POST /api/v1/score-company?include_reasoning=true
```

### Fetch traces separately
```bash
GET /api/v1/traces/{classifier}/{entity_id}
```

## Integration status

| Classifier | Status |
|------------|--------|
| EEM | Planned |
| NSA | Planned |
| RKR | Planned |
| Tarkov | Planned |
| Market | Planned |

## Usage

```python
from reasoning import ReasoningTrace

trace = ReasoningTrace(
    module="trust_web",
    firm_id=123,
    decision="Created CONNECTION edge",
    evidence="Both firms share same director",
    confidence=0.85
)
trace.save()
```

## Benefits

- **Transparency** - Users see why decisions were made
- **Auditability** - Full trail for compliance
- **Debugging** - Detailed classifier behavior inspection
- **Trust** - Explainable AI for stakeholders