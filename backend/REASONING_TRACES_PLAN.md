# Reasoning Traces Implementation Plan

## Overview

This document outlines the strategy for implementing **domain-specific reasoning traces** at every classifier in the Trust Trace backend. Reasoning traces will capture the decision-making logic of each classifier, enabling:

- **Transparency**: Frontend users can see why each classifier made a decision
- **Auditability**: All reasoning is persisted to the database
- **Debugging**: Engineers can inspect classifier behavior in detail
- **Trust**: Stakeholders can validate classification decisions

---

## Current Classifier Inventory

### 1. **EEM** (Event Enrichment Module)
**Location**: `eem/llm/_analyzer.py`, `eem/_pipeline.py`

**Purpose**: Enriches extracted events with LLM-based sentiment, impact, and keyword analysis

**Key Decision Points**:
- LLM availability: fallback to deterministic analysis vs. LLM-based
- Sentiment calculation from event context
- Impact scoring from event type and keywords
- Source tier classification (tier-1, tier-2, tier-3)
- Keyword extraction and deduplication

**Current Output**: `_EventFields` (sentiment, impact, source_tier, keywords, excerpt, entities)

**Domain-Specific Trace Fields**:
```python
EEMReasoningTrace:
  - model_used: str ("llm" | "deterministic")
  - fallback_reason: str | None (if deterministic fallback triggered)
  - sentiment_calculation: {
      base_sentiment: float,
      event_type: str,
      keyword_influences: list[str],
      final_sentiment: float
    }
  - impact_scoring: {
      baseline_impact: float,
      risk_level: int,
      keyword_boost: float,
      final_impact: float
    }
  - source_tier_logic: {
      tier_assigned: str,
      authority_indicators: list[str],  // e.g., ["prokuratura", "knf"]
      reasoning: str
    }
  - keyword_extraction: {
      extracted_keywords: list[str],
      dedup_count: int,
      top_6_keywords: list[str]
    }
```

---

### 2. **NSA** (Non-Sanctioned Analysis)
**Location**: `nsa/scoring/rules.py`, `nsa/scoring/service.py`

**Purpose**: Scores people and companies based on sanctions, warning lists, fraud allegations, and other evidence

**Key Decision Points**:
- Evidence aggregation per person
- Claim weight application (warning_list_hit: 0.85, sanctions_hit: 0.95, etc.)
- Source multiplier calculation (warning_list: 1.0, sanctions: 1.0, registry: 0.85, news: 0.6)
- Official source bonus application
- Cap logic when multiple news-only sources exist

**Current Output**: `PersonScoreResult` (person_risk_score, analysis)

**Domain-Specific Trace Fields**:
```python
NSAReasoningTrace:
  - evidence_summary: {
      total_evidence_count: int,
      evidence_by_source: dict[str, int],  // {"sanctions": 2, "news": 3, ...}
      evidence_by_claim_type: dict[str, int]
    }
  - scoring_breakdown: [
      {
        evidence_id: int,
        source_kind: str,
        claim_type: str,
        claim_weight: float,
        source_multiplier: float,
        severity: float,
        confidence: float,
        official_bonus: float,
        contribution_to_score: float
      },
      ...
    ]
  - aggregation_logic: {
      raw_score: float,
      clamped_score: float,  // max(0.0, min(1.0, raw_score))
      news_only_cap_applied: bool,
      news_only_cap_value: float | None
    }
  - person_context: {
      person_id: int,
      person_name: str,
      role: str | None,
      evidence_sources_hit: list[str]
    }
```

---

### 3. **RKR** (Risk Keyword Recognition)
**Location**: `rkr/scanner/article_scorer.py`, `rkr/pipeline/processor.py`

**Purpose**: Scans articles for risk-related keywords and calculates risk scores

**Key Decision Points**:
- Keyword matching per language
- Title vs. body context weighting (title_multiplier: 1.5)
- Risk score normalization (divided by 3.0)
- Category aggregation from matched keywords
- Threshold passing logic (default: 0.3)

**Current Output**: `RkrResult` (matched_keywords, categories_hit, risk_score, passed_threshold)

**Domain-Specific Trace Fields**:
```python
RKRReasoningTrace:
  - language_detected: str
  - keyword_matches: [
      {
        keyword: str,
        category: str,
        weight: float,
        in_title: bool,
        context_snippet: str,  // 50-100 chars around match
        occurrences: int,
        contribution_to_score: float  // weight * (1.5 if in_title else 1.0)
      },
      ...
    ]
  - score_calculation: {
      raw_sum: float,  // sum of all (weight * title_multiplier?)
      normalization_divisor: float,  // 3.0
      final_risk_score: float,
      capped_at_1_0: bool
    }
  - categories_aggregated: {
      unique_categories: list[str],
      category_hit_counts: dict[str, int]  // {"money_laundering": 2, "fraud": 1, ...}
    }
  - threshold_decision: {
      threshold_applied: float,
      risk_score: float,
      passed: bool,
      margin: float  // risk_score - threshold (positive = pass, negative = fail)
    }
```

---

### 4. **Tarkov** (Event Extraction)
**Location**: `tarkov/extraction/event_extractor.py`

**Purpose**: Extracts AML/fraud events from articles using keyword matching and LLM analysis

**Key Decision Points**:
- Event type classification (keyword-based vs. LLM-based)
- Confidence calculation: `0.55 + (0.1 * min(4, len(keyword_hits)))`
- Risk level assignment: baseline + boost for keyword count
- Title generation
- Source reference creation

**Current Output**: `EventExtraction` (event_type, title, description, risk_level, confidence)

**Domain-Specific Trace Fields**:
```python
TarkovReasoningTrace:
  - extraction_method: str ("keyword_based" | "llm_based")
  - keyword_matching: {
      event_type: str,
      keywords_searched: list[str],  // from AML_KEYWORDS[event_type]
      keywords_found: list[str],
      hit_sentences: list[str],  // sentences containing hits
      deduped_hit_count: int
    }
  - confidence_calculation: {
      base_confidence: float,  // 0.55
      keyword_count: int,
      keyword_boost: float,  // 0.1 * min(4, len(unique_keywords_found))
      final_confidence: float
    }
  - risk_level_assignment: {
      event_type: str,
      baseline_risk: int,  // from mapping: money_laundering=8, fraud=8, etc.
      keyword_count: int,
      boost_value: int,  // min(2, max(0, len(unique_keywords) - 1))
      final_risk_level: int  // max(1, min(10, baseline + boost))
    }
  - title_generation: {
      article_title: str,
      template_used: str | None,  // if applicable
      generated_title: str
    }
  - source_reference: {
      url: str,
      source_title: str,
      credibility_score: float,
      language: str,
      published_at: datetime
    }
```

---

### 5. **Market** (Price & Listing Analysis)
**Location**: `market/pipeline/fetcher.py`, `market/lookup/ticker_search.py`

**Purpose**: Fetches market data (OHLCV) for companies and persists to database

**Key Decision Points**:
- Ticker search strategy (exact match vs. fuzzy matching)
- Listing selection when multiple matches found
- Exchange selection logic
- Data fetch success/failure handling
- Bar count and date range selection

**Current Output**: `FetchResult` (found, charts, firm_id, firm_name)

**Domain-Specific Trace Fields**:
```python
MarketReasoningTrace:
  - ticker_search: {
      firm_name: str,
      search_strategy: str,  // "exact" | "fuzzy" | "partial"
      candidates_found: int,
      matching_process: [
        {
          candidate_name: str,
          ticker: str,
          exchange: str,
          match_score: float,
          selected: bool,
          reason: str  // "highest_score" | "manual_selection" | etc.
        },
        ...
      ]
    }
  - listing_selection: {
      listings_considered: int,
      selected_listings: [
        {
          tv_symbol: str,
          tv_exchange: str,
          ticker: str,
          exchange: str
        },
        ...
      ]
    }
  - fetch_results: {
      listings_processed: int,
      successful_fetches: int,
      failed_fetches: int,
      by_listing: [
        {
          tv_symbol: str,
          tv_exchange: str,
          bars_fetched: int,
          bars_persisted: int,
          data_completeness: float,  // %
          error: str | None
        },
        ...
      ]
    }
  - fetch_parameters: {
      n_bars_requested: int,
      date_range: {
        start_date: datetime | None,
        end_date: datetime | None,
        days_back: int
      }
    }
```

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)

**Create `backend/reasoning/` module**:

```
backend/reasoning/
├── __init__.py
├── base.py                 # Abstract base classes
├── schemas.py              # Pydantic schemas for traces
├── collectors/
│   ├── __init__.py
│   ├── eem_collector.py
│   ├── nsa_collector.py
│   ├── rkr_collector.py
│   ├── tarkov_collector.py
│   └── market_collector.py
├── storage.py              # Database persistence utilities
└── formatters.py           # Human-readable output
```

**Key Files**:

1. **`schemas.py`** — Define domain-specific trace types:
   - `EEMReasoningTrace`
   - `NSAReasoningTrace`
   - `RKRReasoningTrace`
   - `TarkovReasoningTrace`
   - `MarketReasoningTrace`
   - Base `ReasoningTrace` union type

2. **`base.py`** — Abstract collector interface:
   ```python
   class ReasoningTraceCollector(ABC):
       @abstractmethod
       def collect(self, **kwargs) -> ReasoningTrace:
           pass
   ```

3. **`storage.py`** — Database models and repositories:
   - `ReasoningTraceModel` SQLAlchemy model
   - `ReasoningTraceRepository` for CRUD operations
   - Methods: `save()`, `get_by_event_id()`, `get_by_correlation_id()`

---

### Phase 2: Database Schema (Week 1)

**Create migration for reasoning_traces table**:

```sql
CREATE TABLE reasoning_traces (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  classifier_name VARCHAR(50) NOT NULL,
  entity_type VARCHAR(100) NOT NULL,  -- "event", "person", "article", etc.
  entity_id VARCHAR(255) NOT NULL,    -- event_id, person_id, article_id, etc.
  correlation_id VARCHAR(255),        -- links to parent event/article
  trace_data JSONB NOT NULL,          -- domain-specific trace object
  created_at DATETIME DEFAULT NOW(),
  INDEX (classifier_name, created_at),
  INDEX (correlation_id),
  INDEX (entity_id)
);
```

---

### Phase 3: Per-Classifier Integration (Weeks 2-3)

#### **3.1 EEM Integration**

**File**: `eem/llm/_analyzer.py`

Modifications:
```python
from reasoning.collectors.eem_collector import EEMTraceCollector

def _analyze_event(event: _EventRow, firm_name: str) -> tuple[_EventFields, EEMReasoningTrace]:
    user_msg = build_user_message(event, firm_name)
    collector = EEMTraceCollector(event, firm_name)
    
    try:
        raw = chat_completion([...])
        fields = _parse_response(raw)
        collector.record_llm_success(fields, raw)
    except Exception as exc:
        fields = _fallback_fields(event, firm_name)
        collector.record_fallback(exc)
    
    trace = collector.collect()
    return fields, trace
```

**File**: `eem/_pipeline.py`

Modifications:
- Store traces in database after analyzing each event
- Link traces to enrichment records via correlation_id

#### **3.2 NSA Integration**

**File**: `nsa/scoring/rules.py`

Modifications:
```python
from reasoning.collectors.nsa_collector import NSATraceCollector

def score_person(person: PersonScoreInput) -> tuple[PersonScoreResult, NSAReasoningTrace]:
    collector = NSATraceCollector(person)
    
    for item in person.evidence:
        score += ...
        collector.record_evidence_contribution(item, score_delta)
    
    trace = collector.collect()
    return result, trace
```

**File**: `nsa/scoring/service.py`

Modifications:
- Store traces after person scoring
- Link person score to reasoning trace

#### **3.3 RKR Integration**

**File**: `rkr/scanner/article_scorer.py`

Modifications:
```python
from reasoning.collectors.rkr_collector import RKRTraceCollector

def score_article(matches, threshold):
    collector = RKRTraceCollector(matches, threshold)
    
    risk_score = compute_risk_score(matches)
    collector.record_score_calculation(matches, risk_score)
    
    categories_hit = list({m.category for m in matches})
    collector.record_categories(categories_hit)
    
    passed = risk_score >= threshold
    collector.record_threshold_decision(passed)
    
    trace = collector.collect()
    return (risk_score, categories_hit, passed), trace
```

**File**: `rkr/pipeline/processor.py`

Modifications:
- Store traces after article processing
- Link to article via correlation_id

#### **3.4 Tarkov Integration**

**File**: `tarkov/extraction/event_extractor.py`

Modifications:
```python
from reasoning.collectors.tarkov_collector import TarkovTraceCollector

def extract_events_keyword_based(self, article) -> tuple[list[EventExtraction], dict]:
    traces = {}
    
    for event_type, rows in grouped.items():
        collector = TarkovTraceCollector(event_type, rows, article)
        
        # Record keyword matching
        collector.record_keyword_matching(rows)
        
        # Record confidence calculation
        confidence = 0.55 + (0.1 * min(4, len(set(hits))))
        collector.record_confidence(confidence)
        
        # Record risk level
        risk_level = ...
        collector.record_risk_level(risk_level)
        
        traces[event_type] = collector.collect()
    
    return events, traces
```

**File**: `tarkov/pipeline/processor.py`

Modifications:
- Store traces after event extraction
- Associate traces with events

#### **3.5 Market Integration**

**File**: `market/pipeline/fetcher.py`

Modifications:
```python
from reasoning.collectors.market_collector import MarketTraceCollector

def fetch_company(self, firm_id, firm_name, days=365) -> tuple[FetchResult, MarketReasoningTrace]:
    collector = MarketTraceCollector(firm_name)
    
    listings = self._search.find_listings(firm_name)
    collector.record_ticker_search(listings)
    
    charts = []
    for listing in listings:
        collector.record_listing_selected(listing)
        
        records = self._adapter.fetch(...)
        collector.record_fetch_result(listing, records)
        
        charts.append(ChartData(listing=listing, records=records))
    
    trace = collector.collect()
    return FetchResult(...), trace
```

---

### Phase 4: Response Schema Updates (Week 3)

Update all response schemas to optionally include traces:

**`eem/_types.py`**:
```python
@dataclass
class _EventFields:
    sentiment: float
    impact: float
    source_tier: str
    keywords: list[str]
    excerpt: str
    entities: list[str]
    reasoning_trace: EEMReasoningTrace | None = None  # NEW
```

**`nsa/schemas/api.py`**:
```python
class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float
    people_scored: int
    evidence_count: int
    reasoning_traces: list[NSAReasoningTrace] | None = None  # NEW (optional)
```

**`rkr/schemas/rkr_result.py`**:
```python
class RkrResult(BaseModel):
    matched_keywords: list[RkrMatch]
    categories_hit: list[str]
    risk_score: float
    passed_threshold: bool
    reasoning_trace: RKRReasoningTrace | None = None  # NEW
```

**`tarkov/schemas/parsed_result.py`**:
```python
class EventExtraction(BaseModel):
    event_type: str
    event_category: str = "classical"
    title: str
    description: str
    risk_level: int
    occurred_at: datetime
    confidence: float
    source_text: str
    source_reference: SourceReference
    reasoning_trace: TarkovReasoningTrace | None = None  # NEW
```

---

### Phase 5: API Endpoint Updates (Week 4)

Add optional `include_reasoning=true` query parameter to all classifier endpoints:

**EEM API** (if exists):
```
GET /api/v1/enrichment/{event_id}?include_reasoning=true
```

**NSA API**:
```
POST /api/v1/score-company
{
  "firm_id": 123,
  "correlation_id": "...",
  "include_reasoning": true
}
```

**RKR API** (if exposed):
```
POST /api/v1/scan-article
{
  "article": {...},
  "include_reasoning": true
}
```

**Tarkov API**:
```
POST /v1/articles?include_reasoning=true
```

---

### Phase 6: Frontend Integration (Week 5+)

- Design UI components for displaying reasoning traces
- Create trace viewer/explorer tools
- Add filtering and search capabilities by classifier, entity type, date range
- Export traces to JSON/CSV for analysis

---

## Storage Strategy

### Database Persistence

All reasoning traces are **always** stored in the `reasoning_traces` table:
- Indexed by `classifier_name`, `correlation_id`, `entity_id`
- JSONB column for domain-specific trace data
- Automatic pruning policy: retain traces for 90 days (configurable)

### API Response Inclusion

- Traces are **excluded from responses by default** (performance)
- Include only when explicitly requested: `?include_reasoning=true`
- Or fetch separately via trace query API:
  ```
  GET /api/v1/traces/{classifier}/{entity_id}
  ```

---

## Data Model Example

### Raw Trace Storage (Database)

```json
{
  "classifier_name": "RKR",
  "entity_type": "article",
  "entity_id": "article_12345",
  "correlation_id": "corr_67890",
  "trace_data": {
    "language_detected": "en",
    "keyword_matches": [
      {
        "keyword": "money laundering",
        "category": "financial_crime",
        "weight": 0.8,
        "in_title": true,
        "context_snippet": "...suspected money laundering scheme...",
        "occurrences": 2,
        "contribution_to_score": 1.2
      }
    ],
    "score_calculation": {
      "raw_sum": 3.8,
      "normalization_divisor": 3.0,
      "final_risk_score": 0.633,
      "capped_at_1_0": false
    },
    "threshold_decision": {
      "threshold_applied": 0.3,
      "risk_score": 0.633,
      "passed": true,
      "margin": 0.333
    }
  },
  "created_at": "2026-04-28T06:47:51Z"
}
```

---

## Implementation Checklist

- [ ] Create `backend/reasoning/` module structure
- [ ] Define all 5 domain-specific trace schemas
- [ ] Create base `ReasoningTraceCollector` ABC
- [ ] Implement database migration and models
- [ ] Create `EEMTraceCollector` class
- [ ] Integrate reasoning traces into EEM pipeline
- [ ] Create `NSATraceCollector` class
- [ ] Integrate reasoning traces into NSA pipeline
- [ ] Create `RKRTraceCollector` class
- [ ] Integrate reasoning traces into RKR pipeline
- [ ] Create `TarkovTraceCollector` class
- [ ] Integrate reasoning traces into Tarkov pipeline
- [ ] Create `MarketTraceCollector` class
- [ ] Integrate reasoning traces into Market pipeline
- [ ] Update all response schemas to include optional traces
- [ ] Add `include_reasoning` query parameter to all APIs
- [ ] Write unit tests for each collector
- [ ] Write integration tests for end-to-end tracing
- [ ] Create trace query/fetch API endpoints
- [ ] Document trace data model and formats
- [ ] Frontend trace viewer implementation

---

## Benefits & Success Metrics

### For Users
- ✅ Full transparency into why decisions were made
- ✅ Ability to audit and validate classifications
- ✅ Trust in system through explainability

### For Engineers
- ✅ Detailed debugging information for troubleshooting
- ✅ Performance insights (where time/resources spent)
- ✅ Model behavior validation and monitoring

### For Business
- ✅ Compliance: full audit trail of all decisions
- ✅ Risk mitigation: catch classifier errors early
- ✅ Continuous improvement: data for model retraining

---

## Next Steps

1. **Approve** this plan and domain-specific trace schemas
2. **Begin Phase 1** infrastructure development
3. **Coordinate** with frontend team on trace viewer requirements
4. **Schedule** integration sprints for each classifier
