# REASONING TRACES - EXACT FIX LOCATIONS

## FIX #1: Repository Save Method (CRITICAL)

**File:** `backend/reasoning/storage.py`  
**Lines:** 44-54  
**Change Type:** Add commit

### Current Code:
```python
def save(
    self,
    classifier_name: str,
    entity_type: str,
    entity_id: str,
    trace_data: dict,
    correlation_id: Optional[str] = None,
) -> int:
    """Save a reasoning trace to the database."""
    trace_json = json.dumps(trace_data, ensure_ascii=False, default=str)

    model = ReasoningTraceModel(
        classifier_name=classifier_name,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        trace_data=trace_json,
        created_at=datetime.utcnow(),
    )
    self._db.add(model)
    self._db.flush()
    return model.id
```

### Fixed Code:
```python
def save(
    self,
    classifier_name: str,
    entity_type: str,
    entity_id: str,
    trace_data: dict,
    correlation_id: Optional[str] = None,
) -> int:
    """Save a reasoning trace to the database."""
    trace_json = json.dumps(trace_data, ensure_ascii=False, default=str)

    model = ReasoningTraceModel(
        classifier_name=classifier_name,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        trace_data=trace_json,
        created_at=datetime.utcnow(),
    )
    self._db.add(model)
    self._db.flush()
    self._db.commit()  # ← ADD THIS LINE
    return model.id
```

---

## FIX #2: EEM Pipeline

**File:** `backend/eem/_pipeline.py`  
**Lines:** 75-87  
**Change Type:** Add commit after trace save

### Current Code (Lines 75-87):
```python
        # Phase 1: LLM enrichment per event (unchanged — not bucket-dependent)
        impact_map: dict[str, tuple[float, list[str]]] = {}
        for event in events:
            try:
                fields, trace = _analyze_event(event, firm_name)
                enrichment_repo.upsert(event.event_id, fields, config.EEM_MODEL)
                trace_repo.save(
                    classifier_name="EEM",
                    entity_type="event",
                    entity_id=event.event_id,
                    trace_data=trace.model_dump(),
                    correlation_id=None,
                )
                fields.reasoning_trace = trace
                impact_map[event.event_id] = (fields.impact, fields.keywords)
```

### Fixed Code:
```python
        # Phase 1: LLM enrichment per event (unchanged — not bucket-dependent)
        impact_map: dict[str, tuple[float, list[str]]] = {}
        for event in events:
            try:
                fields, trace = _analyze_event(event, firm_name)
                enrichment_repo.upsert(event.event_id, fields, config.EEM_MODEL)
                trace_repo.save(
                    classifier_name="EEM",
                    entity_type="event",
                    entity_id=event.event_id,
                    trace_data=trace.model_dump(),
                    correlation_id=None,
                )
                db.commit()  # ← ADD THIS LINE
                fields.reasoning_trace = trace
                impact_map[event.event_id] = (fields.impact, fields.keywords)
```

---

## FIX #3: NSA Scoring Service

**File:** `backend/nsa/scoring/service.py`  
**Lines:** 50-57  
**Change Type:** Add conditional commit

### Current Code (Lines 50-61):
```python
            person_input = PersonScoreInput(
                person_id=person.id,
                person_name=getattr(person, "name", ""),
                role=getattr(person, "role", None),
                evidence=tuple(evidence),
            )
            result, trace = score_person(person_input)
            
            if trace_repo:
                trace_repo.save(
                    classifier_name="NSA",
                    entity_type="person",
                    entity_id=str(person.id),
                    trace_data=trace.model_dump(),
                    correlation_id=correlation_id,
                )

            person_scores.append(result.person_risk_score)
```

### Fixed Code:
```python
            person_input = PersonScoreInput(
                person_id=person.id,
                person_name=getattr(person, "name", ""),
                role=getattr(person, "role", None),
                evidence=tuple(evidence),
            )
            result, trace = score_person(person_input)
            
            if trace_repo:
                trace_repo.save(
                    classifier_name="NSA",
                    entity_type="person",
                    entity_id=str(person.id),
                    trace_data=trace.model_dump(),
                    correlation_id=correlation_id,
                )
                if db_session:
                    db_session.commit()  # ← ADD THIS LINE

            person_scores.append(result.person_risk_score)
```

---

## FIX #4: Tarkov Processor

**File:** `backend/tarkov/pipeline/processor.py`  
**Lines:** 100-115  
**Change Type:** Add commit after loop

### Current Code (Lines 100-115):
```python
            # Store event extraction traces and embed in EventExtraction objects
            trace_repo = ReasoningTraceRepository(self.db_session)
            for event_type, trace in event_traces.items():
                trace_repo.save(
                    classifier_name="Tarkov",
                    entity_type="event_extraction",
                    entity_id=f"{article_id}_{event_type}",
                    trace_data=trace.model_dump(),
                    correlation_id=correlation_id,
                )
            for event in events:
                if event.event_type in event_traces:
                    event.reasoning_trace = event_traces[event.event_type]
            
            people = self.person_extractor.extract_people(article, [e.description for e in events])
```

### Fixed Code:
```python
            # Store event extraction traces and embed in EventExtraction objects
            trace_repo = ReasoningTraceRepository(self.db_session)
            for event_type, trace in event_traces.items():
                trace_repo.save(
                    classifier_name="Tarkov",
                    entity_type="event_extraction",
                    entity_id=f"{article_id}_{event_type}",
                    trace_data=trace.model_dump(),
                    correlation_id=correlation_id,
                )
            self.db_session.commit()  # ← ADD THIS LINE
            for event in events:
                if event.event_type in event_traces:
                    event.reasoning_trace = event_traces[event.event_type]
            
            people = self.person_extractor.extract_people(article, [e.description for e in events])
```

---

## OPTIONAL: RKR Traces Implementation

### File to Create: `backend/reasoning/collectors/rkr_collector.py`

```python
"""Reasoning trace collector for RKR (Risk Keyword Recognition)."""

from __future__ import annotations

from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import (
    # Note: Schema needs to be created first in schemas.py
)

@TraceCollectorRegistry.register("RKR")
class RKRTraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during RKR keyword scanning."""
    
    def __init__(self, article_id: str):
        """Initialize collector for article RKR scoring.
        
        Args:
            article_id: ID of the article being scored
        """
        self.article_id = article_id
        self.language_detected: str | None = None
        self.keyword_matches: list = []
        self.raw_score: float | None = None
        self.normalized_score: float | None = None
        self.categories: list[str] = []
    
    def record_language_detection(self, language: str) -> None:
        """Record detected language."""
        self.language_detected = language
    
    def record_keyword_match(self, keyword: str, category: str, weight: float,
                            in_title: bool, context: str, occurrences: int) -> None:
        """Record a keyword match."""
        self.keyword_matches.append({
            "keyword": keyword,
            "category": category,
            "weight": weight,
            "in_title": in_title,
            "context": context[:100],
            "occurrences": occurrences,
            "contribution": weight * (1.5 if in_title else 1.0),
        })
    
    def record_score_calculation(self, raw_score: float, normalized_score: float,
                                normalization_divisor: float) -> None:
        """Record score calculation details."""
        self.raw_score = raw_score
        self.normalized_score = normalized_score
        self.normalization_divisor = normalization_divisor
    
    def record_categories(self, categories: list[str]) -> None:
        """Record unique categories found."""
        self.categories = categories
    
    def collect(self):
        """Collect and return the RKR reasoning trace."""
        from reasoning.schemas import RKRReasoningTrace
        return RKRReasoningTrace(
            article_id=self.article_id,
            language_detected=self.language_detected,
            keyword_matches=self.keyword_matches,
            score_calculation={
                "raw_score": self.raw_score or 0.0,
                "normalized_score": self.normalized_score or 0.0,
                "normalization_divisor": getattr(self, "normalization_divisor", 3.0),
            },
            categories_found=self.categories,
        )
```

### Schema Addition: `backend/reasoning/schemas.py`

Add after line 280 (after Tarkov section):

```python
# ============================================================================
# RKR Reasoning Trace
# ============================================================================

class RKRKeywordMatch(BaseModel):
    """Details of a matched keyword."""
    keyword: str
    category: str
    weight: float
    in_title: bool
    context: str
    occurrences: int
    contribution: float

class RKRScoreCalculation(BaseModel):
    """Score calculation breakdown for RKR."""
    raw_score: float
    normalized_score: float
    normalization_divisor: float

class RKRReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for RKR classifier."""
    article_id: str
    language_detected: Optional[str] = None
    keyword_matches: list[RKRKeywordMatch] = []
    score_calculation: RKRScoreCalculation
    categories_found: list[str] = []
```

### Union Type Update: `backend/reasoning/schemas.py`

Update line 280 (ReasoningTraceData union):

```python
ReasoningTraceData = Union[
    EEMReasoningTrace,
    NSAReasoningTrace,
    TarkovReasoningTrace,
    MarketReasoningTrace,
    RKRReasoningTrace,  # ← ADD THIS
]
```

---

## Verification Checklist

After applying fixes:

- [ ] `backend/reasoning/storage.py` has `self._db.commit()` at line 54
- [ ] `backend/eem/_pipeline.py` has `db.commit()` after trace save
- [ ] `backend/nsa/scoring/service.py` has `db_session.commit()` after trace save
- [ ] `backend/tarkov/pipeline/processor.py` has `self.db_session.commit()` after trace loop
- [ ] Run `python run_traces_demo.py` completes without errors
- [ ] Check `sqlite3 test_traces.db "SELECT COUNT(*) FROM reasoning_traces"` returns > 0
- [ ] Verify trace data contains expected fields

---

## Testing After Fixes

```bash
cd backend
.venv\Scripts\activate

# Run demo
python run_traces_demo.py

# Verify persistence
sqlite3 test_traces.db << EOF
SELECT classifier_name, COUNT(*) as count FROM reasoning_traces GROUP BY classifier_name;
EOF

# Expected output:
# NSA|2
# (Other classifiers depend on pipeline execution)
```
