"""Test Stage 4: Response Schema Updates with Reasoning Traces"""

import json
from datetime import datetime

from eem._types import _EventFields
from nsa.schemas.api import PersonScoreSummary, ScoreCompanyResponse
from rkr.schemas.rkr_result import RkrResult, RkrMatch
from tarkov.schemas.parsed_result import EventExtraction, SourceReference
from market.schemas.ohlcv import FetchResult
from reasoning.schemas import (
    EEMReasoningTrace,
    EEMSentimentCalculation,
    EEMImpactScoring,
    EEMSourceTierLogic,
    EEMKeywordExtraction,
    NSAReasoningTrace,
    NSAEvidenceSummary,
    NSAScoringBreakdownItem,
    NSAAggregationLogic,
    NSAPersonContext,
    TarkovReasoningTrace,
    TarkovKeywordMatching,
    TarkovConfidenceCalculation,
    TarkovRiskLevelAssignment,
    TarkovTitleGeneration,
    TarkovSourceReference,
    MarketReasoningTrace,
    MarketTickerSearch,
    MarketListingSelection,
    MarketFetchResults,
    MarketFetchParameters,
    MarketDateRange,
)


def _make_eem_trace() -> EEMReasoningTrace:
    return EEMReasoningTrace(
        model_used="llm",
        sentiment_calculation=EEMSentimentCalculation(
            base_sentiment=0.5, event_type="fraud", keyword_influences=["fraud"], final_sentiment=0.7
        ),
        impact_scoring=EEMImpactScoring(baseline_impact=5.0, risk_level=7, keyword_boost=1.5, final_impact=6.5),
        source_tier_logic=EEMSourceTierLogic(
            tier_assigned="tier-1", authority_indicators=["knf"], reasoning="Official regulator"
        ),
        keyword_extraction=EEMKeywordExtraction(
            extracted_keywords=["fraud"], dedup_count=1, top_6_keywords=["fraud"]
        ),
    )


def _make_nsa_trace() -> NSAReasoningTrace:
    return NSAReasoningTrace(
        evidence_summary=NSAEvidenceSummary(
            total_evidence_count=2,
            evidence_by_source={"sanctions": 1, "news": 1},
            evidence_by_claim_type={"sanctions_hit": 1, "news_alert": 1},
        ),
        scoring_breakdown=[
            NSAScoringBreakdownItem(
                evidence_id=1,
                source_kind="sanctions",
                claim_type="sanctions_hit",
                claim_weight=0.95,
                source_multiplier=1.0,
                severity=0.9,
                confidence=0.95,
                official_bonus=0.1,
                contribution_to_score=0.95,
            )
        ],
        aggregation_logic=NSAAggregationLogic(raw_score=0.95, clamped_score=0.95, news_only_cap_applied=False),
        person_context=NSAPersonContext(
            person_id=1, person_name="John Doe", role="CEO", evidence_sources_hit=["sanctions"]
        ),
    )


def _make_tarkov_trace() -> TarkovReasoningTrace:
    return TarkovReasoningTrace(
        extraction_method="keyword_based",
        keyword_matching=TarkovKeywordMatching(
            event_type="money_laundering",
            keywords_searched=["money laundering"],
            keywords_found=["money laundering"],
            hit_sentences=["Suspected money laundering."],
            deduped_hit_count=1,
        ),
        confidence_calculation=TarkovConfidenceCalculation(
            base_confidence=0.55, keyword_count=1, keyword_boost=0.1, final_confidence=0.65
        ),
        risk_level_assignment=TarkovRiskLevelAssignment(
            event_type="money_laundering", baseline_risk=8, keyword_count=1, boost_value=0, final_risk_level=8
        ),
        title_generation=TarkovTitleGeneration(
            article_title="Suspected AML", template_used=None, generated_title="Money Laundering Detected"
        ),
        source_reference=TarkovSourceReference(
            url="https://example.com", source_title="News", credibility_score=0.8, language="en"
        ),
    )


def _make_market_trace() -> MarketReasoningTrace:
    return MarketReasoningTrace(
        ticker_search=MarketTickerSearch(
            firm_name="Acme Corp", search_strategy="exact", candidates_found=0, matching_process=[]
        ),
        listing_selection=MarketListingSelection(listings_considered=0, selected_listings=[]),
        fetch_results=MarketFetchResults(
            listings_processed=0, successful_fetches=0, failed_fetches=0, by_listing=[]
        ),
        fetch_parameters=MarketFetchParameters(n_bars_requested=365, date_range=MarketDateRange(days_back=365)),
    )


def test_backwards_compatibility():
    """Test that all schemas work without reasoning traces (backwards compatible)."""
    print("Testing backwards compatibility...")

    event = _EventFields(
        sentiment=0.5, impact=0.7, source_tier="tier-1", keywords=["fraud"], excerpt="...", entities=[]
    )
    assert event.reasoning_trace is None
    print("  EEM _EventFields: OK")

    nsa_response = ScoreCompanyResponse(
        status="ok", firm_id=1, company_risk_score=0.5, people_scored=1, evidence_count=2
    )
    assert nsa_response.people_summaries is None
    print("  NSA ScoreCompanyResponse: OK")

    rkr = RkrResult(matched_keywords=[], categories_hit=[], risk_score=0.4, passed_threshold=True)
    assert not hasattr(rkr, "reasoning_trace")
    print("  RKR RkrResult: OK (no trace field)")

    event_extraction = EventExtraction(
        event_type="fraud",
        title="Fraud",
        description="Desc",
        risk_level=7,
        occurred_at=datetime.now(),
        confidence=0.85,
        source_text="text",
        source_reference=SourceReference(url="http://example.com", title="Ex", source_text="text"),
    )
    assert event_extraction.reasoning_trace is None
    print("  Tarkov EventExtraction: OK")

    fetch_result = FetchResult(firm_id=1, firm_name="Corp", found=True, charts=[])
    assert fetch_result.reasoning_trace is None
    print("  Market FetchResult: OK")

    print("Backwards compatibility: PASSED\n")


def test_with_embedded_traces():
    """Test that full trace objects can be embedded in responses."""
    print("Testing embedded reasoning traces...")

    eem_trace = _make_eem_trace()
    event = _EventFields(
        sentiment=0.7, impact=0.8, source_tier="tier-1", keywords=["fraud"], excerpt="...", entities=[],
        reasoning_trace=eem_trace,
    )
    assert event.reasoning_trace is not None
    assert event.reasoning_trace.model_used == "llm"
    print("  EEM _EventFields with trace: OK")

    nsa_trace = _make_nsa_trace()
    summary = PersonScoreSummary(person_id=1, person_name="John Doe", risk_score=0.9, reasoning_trace=nsa_trace)
    assert summary.reasoning_trace is not None
    response = ScoreCompanyResponse(
        status="ok", firm_id=1, company_risk_score=0.9, people_scored=1, evidence_count=2,
        people_summaries=[summary],
    )
    assert response.people_summaries[0].reasoning_trace.person_context.person_name == "John Doe"
    print("  NSA ScoreCompanyResponse with trace: OK")

    tarkov_trace = _make_tarkov_trace()
    event_extraction = EventExtraction(
        event_type="money_laundering",
        title="AML Event",
        description="Desc",
        risk_level=8,
        occurred_at=datetime.now(),
        confidence=0.65,
        source_text="text",
        source_reference=SourceReference(url="http://example.com", title="Ex", source_text="text"),
        reasoning_trace=tarkov_trace,
    )
    assert event_extraction.reasoning_trace.confidence_calculation.final_confidence == 0.65
    print("  Tarkov EventExtraction with trace: OK")

    market_trace = _make_market_trace()
    fetch_result = FetchResult(firm_id=1, firm_name="Acme", found=False, charts=[], reasoning_trace=market_trace)
    assert fetch_result.reasoning_trace.ticker_search.firm_name == "Acme Corp"
    print("  Market FetchResult with trace: OK")

    print("Embedded traces: PASSED\n")


def test_json_serialization():
    """Test that schemas serialize to JSON correctly."""
    print("Testing JSON serialization...")

    eem_trace = _make_eem_trace()
    event = _EventFields(
        sentiment=0.7, impact=0.8, source_tier="tier-1", keywords=["fraud"], excerpt="...", entities=[],
        reasoning_trace=eem_trace,
    )
    import dataclasses
    d = dataclasses.asdict(event)
    # dataclasses.asdict doesn't recurse into Pydantic models; use model_dump() explicitly
    assert d["reasoning_trace"].model_dump()["model_used"] == "llm"
    print("  EEM _EventFields serialization: OK")

    nsa_trace = _make_nsa_trace()
    summary = PersonScoreSummary(person_id=1, person_name="John", risk_score=0.5, reasoning_trace=nsa_trace)
    response = ScoreCompanyResponse(
        status="ok", firm_id=1, company_risk_score=0.5, people_scored=1, evidence_count=1,
        people_summaries=[summary],
    )
    parsed = json.loads(response.model_dump_json())
    assert parsed["people_summaries"][0]["reasoning_trace"]["aggregation_logic"]["clamped_score"] == 0.95
    print("  NSA ScoreCompanyResponse serialization: OK")

    print("JSON serialization: PASSED\n")


if __name__ == "__main__":
    print("=" * 70)
    print("STAGE 4: RESPONSE SCHEMA UPDATES WITH REASONING TRACES")
    print("=" * 70)
    print()

    test_backwards_compatibility()
    test_with_embedded_traces()
    test_json_serialization()

    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
