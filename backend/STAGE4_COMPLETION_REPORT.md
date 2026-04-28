# Stage 4 Completion Report

Response schema updates across all five classifiers to support optional reasoning traces.

## What it does

Completes response schema updates ensuring:
1. **Backwards Compatibility** - Existing code works unchanged
2. **Optional Traces** - Fields default to None
3. **Type Safety** - Proper type hints for IDE support
4. **Zero-Breaking Changes** - API responses remain valid

## Changes made

### 1. EEM (_EventFields)
**File**: `backend/eem/_types.py`

Added optional `reasoning_trace` field to `_EventFields`:
```python
@dataclass
class _EventFields:
    sentiment: float
    impact: float
    source_tier: str
    keywords: list[str]
    excerpt: str
    entities: list[str]
    reasoning_trace: Optional[EEMReasoningTrace] = None
```

### 2. NSA (ScoreCompanyResponse)
**File**: `backend/nsa/schemas/api.py`

Added optional `reasoning_traces` list to response:
```python
class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float = Field(ge=0.0, le=1.0)
    people_scored: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    reasoning_traces: Optional[list[NSAReasoningTrace]] = None
```

### 3. RKR (RkrResult)
**File**: `backend/rkr/schemas/rkr_result.py`

Added optional `reasoning_trace`:
```python
class RkrResult(BaseModel):
    matched_keywords: list[RkrMatch]
    categories_hit: list[str]
    risk_score: float = Field(ge=0.0, le=1.0)
    passed_threshold: bool
    reasoning_trace: Optional[RKRReasoningTrace] = None
```

### 4. Tarkov (EventExtraction)
**File**: `backend/tarkov/schemas/parsed_result.py`

Added optional `reasoning_trace`:
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
    reasoning_trace: Optional[TarkovReasoningTrace] = None
```

### 5. Market (FetchResult)
**File**: `backend/market/schemas/ohlcv.py`

Added optional `reasoning_trace`:
```python
class FetchResult(BaseModel):
    firm_id: int
    firm_name: str
    found: bool
    charts: list[ChartData]
    reasoning_trace: Optional[MarketReasoningTrace] = None
```

## Backwards compatibility

All changes maintain 100% backwards compatibility:
- Existing code without traces continues to work
- Fields default to None
- JSON serialization excludes None by default
- API responses remain valid

## Example usage

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
    reasoning_traces=[trace1, trace2]
)
```

## Integration points

These changes prepare for:
1. **Phase 3** - Trace collectors populate these fields
2. **Phase 5** - API query parameter `?include_reasoning=true`
3. **Frontend** - Trace viewer UI components
4. **Database** - Traces persisted in reasoning_traces table

## Files modified

1. `backend/eem/_types.py` - Added reasoning_trace to _EventFields
2. `backend/nsa/schemas/api.py` - Added reasoning_traces to ScoreCompanyResponse
3. `backend/rkr/schemas/rkr_result.py` - Added reasoning_trace to RkrResult
4. `backend/tarkov/schemas/parsed_result.py` - Added reasoning_trace to EventExtraction
5. `backend/market/schemas/ohlcv.py` - Added reasoning_trace to FetchResult

## Next steps

1. **Phase 5** - Update APIs with `?include_reasoning=true` parameter
2. **Phase 3** - Implement trace collectors
3. **Frontend** - Build trace viewer UI
4. **Database** - Implement schema and storage

## Checklist

- [x] Update EEM _EventFields with reasoning_trace
- [x] Update NSA ScoreCompanyResponse with reasoning_traces
- [x] Update RKR RkrResult with reasoning_trace
- [x] Update Tarkov EventExtraction with reasoning_trace
- [x] Update Market FetchResult with reasoning_trace
- [x] Add imports for all trace schemas
- [x] Test backwards compatibility
- [x] Verify JSON serialization
- [x] Confirm type safety
- [x] Document all changes

**Status**: COMPLETE
**Date**: 2026-04-28
**Stage**: 4 of 6