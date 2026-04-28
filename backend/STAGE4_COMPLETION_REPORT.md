# Stage 4: Response Schema Updates with Reasoning Traces

## Overview

Stage 4 completes the response schema updates across all five classifiers (EEM, NSA, RKR, Tarkov, and Market) to support optional reasoning traces. This stage ensures that:

1. **Backwards Compatibility**: All existing code continues to work without modification
2. **Optional Traces**: Reasoning traces are optional fields that default to `None`
3. **Type Safety**: All trace fields have proper type hints for IDE support and validation
4. **Zero-Breaking Changes**: Existing API responses remain valid

## Changes Made

### 1. EEM (_EventFields)

**File**: `backend/eem/_types.py`

**Change**:
```python
@dataclass
class _EventFields:
    sentiment: float
    impact: float
    source_tier: str
    keywords: list[str]
    excerpt: str
    entities: list[str]
    reasoning_trace: Optional[EEMReasoningTrace] = None  # NEW
```

**Details**:
- Added optional `reasoning_trace` field
- Type: `Optional[EEMReasoningTrace]` (defaults to `None`)
- Will be populated by EEM trace collectors during event enrichment

### 2. NSA (ScoreCompanyResponse)

**File**: `backend/nsa/schemas/api.py`

**Change**:
```python
class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float = Field(ge=0.0, le=1.0)
    people_scored: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    reasoning_traces: Optional[list[NSAReasoningTrace]] = None  # NEW
```

**Details**:
- Added optional `reasoning_traces` field (list)
- Type: `Optional[list[NSAReasoningTrace]]` (defaults to `None`)
- Will contain reasoning traces for each person scored during company risk assessment

### 3. RKR (RkrResult)

**File**: `backend/rkr/schemas/rkr_result.py`

**Change**:
```python
class RkrResult(BaseModel):
    matched_keywords: list[RkrMatch]
    categories_hit: list[str]
    risk_score: float = Field(ge=0.0, le=1.0)
    passed_threshold: bool
    reasoning_trace: Optional[RKRReasoningTrace] = None  # NEW
```

**Details**:
- Added optional `reasoning_trace` field
- Type: `Optional[RKRReasoningTrace]` (defaults to `None`)
- Will contain keyword matching and scoring breakdown for risk assessment

### 4. Tarkov (EventExtraction)

**File**: `backend/tarkov/schemas/parsed_result.py`

**Change**:
```python
class EventExtraction(BaseModel):
    event_type: str
    event_category: str = "classical"
    title: str
    description: str
    risk_level: int = Field(ge=1, le=10)
    occurred_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference
    reasoning_trace: Optional[TarkovReasoningTrace] = None  # NEW
```

**Details**:
- Added optional `reasoning_trace` field
- Type: `Optional[TarkovReasoningTrace]` (defaults to `None`)
- Will contain event extraction method, keyword matching, and confidence calculation details

### 5. Market (FetchResult)

**File**: `backend/market/schemas/ohlcv.py`

**Change**:
```python
class FetchResult(BaseModel):
    firm_id: int
    firm_name: str
    found: bool
    charts: list[ChartData]
    reasoning_trace: Optional[MarketReasoningTrace] = None  # NEW
```

**Details**:
- Added optional `reasoning_trace` field
- Type: `Optional[MarketReasoningTrace]` (defaults to `None`)
- Will contain ticker search, listing selection, and fetch results breakdown

## Backwards Compatibility

All changes maintain **100% backwards compatibility**:

- Existing code that creates responses **without** reasoning traces continues to work unchanged
- The fields are optional and default to `None`
- JSON serialization excludes `None` fields by default (Pydantic behavior)
- API responses remain valid for existing clients

### Example: Backwards Compatible Usage

```python
# Old code (still works):
response = ScoreCompanyResponse(
    status="success",
    firm_id=123,
    company_risk_score=0.65,
    people_scored=5,
    evidence_count=10
)

# New code (with traces):
response = ScoreCompanyResponse(
    status="success",
    firm_id=123,
    company_risk_score=0.65,
    people_scored=5,
    evidence_count=10,
    reasoning_traces=[trace1, trace2, ...]  # Optional
)
```

## Integration Points

These schema changes prepare the system for:

1. **Phase 3 Integration**: Trace collectors will populate these fields
2. **Phase 5 API Updates**: Query parameter `?include_reasoning=true` will control trace inclusion
3. **Frontend Integration**: Traces can be displayed in the UI when requested
4. **Database Storage**: Traces will be persisted in `reasoning_traces` table

## Testing

All changes have been validated with comprehensive tests:

- **test_stage4_schemas.py**: Tests backwards compatibility, serialization, optional fields, and type correctness
- Run with: `python test_stage4_schemas.py`

### Test Results

```
STAGE 4: RESPONSE SCHEMA UPDATES WITH REASONING TRACES

Testing backwards compatibility... PASSED
Testing JSON serialization... PASSED
Testing optional reasoning trace fields... PASSED
Testing field types... PASSED

ALL TESTS PASSED
```

## Next Steps

1. **Phase 5**: Update API endpoints to accept `?include_reasoning=true` query parameter
2. **Phase 3 Integration**: Implement trace collectors for each classifier
3. **Frontend**: Build trace viewer/explorer UI components
4. **Database**: Implement database schema and trace storage

## Implementation Checklist

- [x] Update EEM `_EventFields` with `reasoning_trace`
- [x] Update NSA `ScoreCompanyResponse` with `reasoning_traces`
- [x] Update RKR `RkrResult` with `reasoning_trace`
- [x] Update Tarkov `EventExtraction` with `reasoning_trace`
- [x] Update Market `FetchResult` with `reasoning_trace`
- [x] Add imports for all trace schemas
- [x] Test backwards compatibility
- [x] Verify JSON serialization
- [x] Confirm type safety
- [x] Document all changes

## Files Modified

1. `backend/eem/_types.py` - Added reasoning_trace to _EventFields
2. `backend/nsa/schemas/api.py` - Added reasoning_traces to ScoreCompanyResponse
3. `backend/rkr/schemas/rkr_result.py` - Added reasoning_trace to RkrResult
4. `backend/tarkov/schemas/parsed_result.py` - Added reasoning_trace to EventExtraction
5. `backend/market/schemas/ohlcv.py` - Added reasoning_trace to FetchResult

## Configuration

No configuration changes needed. The trace fields are optional and default to `None`. They will only be populated when:

1. Trace collectors are integrated (Phase 3)
2. `include_reasoning=true` is passed to APIs (Phase 5)
3. Explicit trace data is provided to response constructors

---

**Status**: COMPLETE
**Date**: 2026-04-28
**Stage**: 4 of 6
