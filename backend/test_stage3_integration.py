"""Test Stage 3: Per-Classifier Integration."""

import json
import sys
from reasoning.collectors.eem_collector import EEMTraceCollector
from reasoning.collectors.nsa_collector import NSATraceCollector
from reasoning.collectors.tarkov_collector import TarkovTraceCollector
from reasoning.collectors.market_collector import MarketTraceCollector
from eem._types import _EventFields

# Ensure UTF-8 output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_eem_collector():
    """Test EEM trace collection."""
    collector = EEMTraceCollector("event_123", "Acme Corp")
    
    fields = _EventFields(
        sentiment=0.5,
        impact=2.0,
        source_tier="tier-1",
        keywords=["risk", "fraud"],
        excerpt="Test excerpt",
        entities=["Acme Corp"],
    )
    
    collector.record_llm_success(fields, '{"sentiment": 0.5}')
    trace = collector.collect()
    
    assert trace.model_used == "llm"
    assert trace.sentiment_calculation.final_sentiment == 0.5
    print("✓ EEM collector test passed")


def test_nsa_collector():
    """Test NSA trace collection."""
    collector = NSATraceCollector(person_id=1, person_name="John Doe")
    
    collector.record_evidence_item(
        evidence_id=1,
        source_kind="sanctions",
        claim_type="sanctions_hit",
        claim_weight=0.95,
        source_multiplier=1.0,
        severity=0.8,
        confidence=0.9,
        official_bonus=0.05,
        contribution_to_score=0.686,
    )
    
    collector.record_score_calculation(
        raw_score=0.686,
        clamped_score=0.686,
    )
    
    trace = collector.collect()
    assert trace.aggregation_logic.raw_score == 0.686
    assert len(trace.scoring_breakdown) == 1
    print("✓ NSA collector test passed")


def test_tarkov_collector():
    """Test Tarkov trace collection."""
    collector = TarkovTraceCollector("money_laundering", "article_456")
    
    collector.record_keyword_extraction(
        keywords_searched=["money laundering", "AML"],
        keywords_found=["money laundering"],
        hit_sentences=["This describes money laundering."],
    )
    
    collector.record_confidence_calculation(
        base_confidence=0.55,
        keyword_count=1,
        keyword_boost=0.1,
        final_confidence=0.65,
    )
    
    collector.record_risk_level(
        baseline_risk=8,
        keyword_count=1,
        boost_value=0,
        final_risk_level=8,
    )
    
    trace = collector.collect()
    assert trace.confidence_calculation.final_confidence == 0.65
    assert trace.risk_level_assignment.final_risk_level == 8
    print("✓ Tarkov collector test passed")


def test_market_collector():
    """Test Market trace collection."""
    collector = MarketTraceCollector("Tesla Inc", 123)
    
    collector.record_ticker_search(
        strategy="exact",
        candidates=[
            {
                "name": "Tesla Inc",
                "ticker": "TSLA",
                "exchange": "NASDAQ",
                "match_score": 1.0,
                "selected": True,
                "reason": "exact_match",
            }
        ],
    )
    
    collector.record_listing_selected(
        tv_symbol="TSLA",
        tv_exchange="NASDAQ",
        ticker="TSLA",
        exchange="NASDAQ",
    )
    
    collector.record_fetch_result(
        tv_symbol="TSLA",
        tv_exchange="NASDAQ",
        bars_fetched=365,
        bars_persisted=365,
    )
    
    trace = collector.collect()
    assert trace.fetch_results.successful_fetches == 1
    print("✓ Market collector test passed")


if __name__ == "__main__":
    test_eem_collector()
    test_nsa_collector()
    test_tarkov_collector()
    test_market_collector()
    print("\n✅ All Stage 3 integration tests passed!")
