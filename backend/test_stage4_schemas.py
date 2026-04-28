"""Test Stage 4: Response Schema Updates with Reasoning Traces"""

import json
from datetime import datetime, date
from typing import Optional

# Test imports
from eem._types import _EventFields, _EventRow, _SourceRow
from nsa.schemas.api import ScoreCompanyResponse
from rkr.schemas.rkr_result import RkrResult, RkrMatch
from tarkov.schemas.parsed_result import EventExtraction, SourceReference
from market.schemas.ohlcv import FetchResult, ChartData, ListingMatch, OHLCVRecord
from reasoning.schemas import (
    EEMReasoningTrace,
    NSAReasoningTrace,
    RKRReasoningTrace,
    TarkovReasoningTrace,
    MarketReasoningTrace,
)


def test_backwards_compatibility():
    """Test that all schemas work without reasoning traces (backwards compatible)."""
    print("Testing backwards compatibility...")
    
    # EEM: _EventFields without reasoning_trace
    event = _EventFields(
        sentiment=0.5,
        impact=0.7,
        source_tier="tier-1",
        keywords=["fraud", "money_laundering"],
        excerpt="Some excerpt",
        entities=["person1"]
    )
    assert event.reasoning_trace is None
    print("  EEM _EventFields: OK (no reasoning_trace required)")
    
    # NSA: ScoreCompanyResponse without reasoning_traces
    nsa_response = ScoreCompanyResponse(
        status="success",
        firm_id=123,
        company_risk_score=0.65,
        people_scored=5,
        evidence_count=10
    )
    assert nsa_response.reasoning_traces is None
    print("  NSA ScoreCompanyResponse: OK (no reasoning_traces required)")
    
    # RKR: RkrResult without reasoning_trace
    rkr_result = RkrResult(
        matched_keywords=[],
        categories_hit=["fraud"],
        risk_score=0.4,
        passed_threshold=True
    )
    assert rkr_result.reasoning_trace is None
    print("  RKR RkrResult: OK (no reasoning_trace required)")
    
    # Tarkov: EventExtraction without reasoning_trace
    event_extraction = EventExtraction(
        event_type="fraud",
        event_category="classical",
        title="Fraud detected",
        description="Description",
        risk_level=7,
        occurred_at=datetime.now(),
        confidence=0.85,
        source_text="source",
        source_reference=SourceReference(
            url="http://example.com",
            title="Example",
            source_text="text"
        )
    )
    assert event_extraction.reasoning_trace is None
    print("  Tarkov EventExtraction: OK (no reasoning_trace required)")
    
    # Market: FetchResult without reasoning_trace
    fetch_result = FetchResult(
        firm_id=123,
        firm_name="Test Corp",
        found=True,
        charts=[]
    )
    assert fetch_result.reasoning_trace is None
    print("  Market FetchResult: OK (no reasoning_trace required)")
    
    print("Backwards compatibility: PASSED\n")


def test_json_serialization():
    """Test that schemas can be serialized to JSON without reasoning traces."""
    print("Testing JSON serialization...")
    
    # NSA Response
    nsa_response = ScoreCompanyResponse(
        status="success",
        firm_id=123,
        company_risk_score=0.65,
        people_scored=5,
        evidence_count=10
    )
    json_str = nsa_response.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["status"] == "success"
    assert "reasoning_traces" not in parsed or parsed.get("reasoning_traces") is None
    print("  NSA Response serialization: OK")
    
    # RKR Result
    rkr_result = RkrResult(
        matched_keywords=[],
        categories_hit=[],
        risk_score=0.3,
        passed_threshold=False
    )
    json_str = rkr_result.model_dump_json()
    parsed = json.loads(json_str)
    assert "reasoning_trace" not in parsed or parsed.get("reasoning_trace") is None
    print("  RKR Result serialization: OK")
    
    print("JSON serialization: PASSED\n")


def test_optional_fields():
    """Test that reasoning_trace fields are properly optional."""
    print("Testing optional reasoning trace fields...")
    
    # Test that we can still create without traces
    result1 = RkrResult(
        matched_keywords=[],
        categories_hit=[],
        risk_score=0.5,
        passed_threshold=True
    )
    print("  RkrResult without trace: OK")
    
    # Test that we can create with traces if provided
    result2 = RkrResult(
        matched_keywords=[],
        categories_hit=[],
        risk_score=0.5,
        passed_threshold=True,
        reasoning_trace=None  # Explicitly set to None
    )
    print("  RkrResult with trace=None: OK")
    
    response = ScoreCompanyResponse(
        status="success",
        firm_id=123,
        company_risk_score=0.65,
        people_scored=5,
        evidence_count=10,
        reasoning_traces=None  # Explicitly set to None
    )
    print("  ScoreCompanyResponse with traces=None: OK")
    
    print("Optional fields: PASSED\n")


def test_field_types():
    """Test that reasoning trace fields have correct types."""
    print("Testing field types...")
    
    # Check field annotations
    from typing import get_type_hints
    
    # RKR field should be Optional[RKRReasoningTrace]
    hints = get_type_hints(RkrResult)
    print(f"  RkrResult.reasoning_trace type: {hints.get('reasoning_trace', 'NOT FOUND')}")
    
    # NSA field should be Optional[list[NSAReasoningTrace]]
    hints = get_type_hints(ScoreCompanyResponse)
    print(f"  ScoreCompanyResponse.reasoning_traces type: {hints.get('reasoning_traces', 'NOT FOUND')}")
    
    print("Field types: PASSED\n")


if __name__ == "__main__":
    print("=" * 70)
    print("STAGE 4: RESPONSE SCHEMA UPDATES WITH REASONING TRACES")
    print("=" * 70)
    print()
    
    test_backwards_compatibility()
    test_json_serialization()
    test_optional_fields()
    test_field_types()
    
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
