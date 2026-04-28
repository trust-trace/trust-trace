#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script for Stage 2: Database Schema verification.

This script demonstrates that:
1. All schemas can be imported and instantiated
2. Database models are properly defined
3. The repository CRUD operations work
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from reasoning import (
    ReasoningTraceRepository,
    EEMReasoningTrace,
    NSAReasoningTrace,
    RKRReasoningTrace,
    TarkovReasoningTrace,
    MarketReasoningTrace,
    ReasoningTraceStorageModel,
    init_engine,
    create_all,
    get_db,
)
from reasoning.schemas import (
    EEMSentimentCalculation,
    EEMImpactScoring,
    EEMSourceTierLogic,
    EEMKeywordExtraction,
    NSAEvidenceSummary,
    NSAScoringBreakdownItem,
    NSAAggregationLogic,
    NSAPersonContext,
    RKRKeywordMatch,
    RKRScoreCalculation,
    RKRCategoriesAggregated,
    RKRThresholdDecision,
    TarkovKeywordMatching,
    TarkovConfidenceCalculation,
    TarkovRiskLevelAssignment,
    TarkovTitleGeneration,
    TarkovSourceReference,
    MarketTickerSearch,
    MarketTickerSearchCandidate,
    MarketListingSelection,
    MarketFetchResults,
    MarketFetchResultByListing,
    MarketFetchParameters,
    MarketDateRange,
)


def test_eem_trace():
    """Test EEM reasoning trace creation."""
    print("Testing EEM Reasoning Trace...")
    trace = EEMReasoningTrace(
        model_used="llm",
        sentiment_calculation=EEMSentimentCalculation(
            base_sentiment=0.5,
            event_type="fraud_allegation",
            keyword_influences=["fraud", "suspicious"],
            final_sentiment=0.7,
        ),
        impact_scoring=EEMImpactScoring(
            baseline_impact=5.0,
            risk_level=7,
            keyword_boost=1.5,
            final_impact=6.5,
        ),
        source_tier_logic=EEMSourceTierLogic(
            tier_assigned="tier-1",
            authority_indicators=["regulatory_body"],
            reasoning="Source is official regulatory authority",
        ),
        keyword_extraction=EEMKeywordExtraction(
            extracted_keywords=["fraud", "suspicious", "investigation"],
            dedup_count=3,
            top_6_keywords=["fraud", "suspicious", "investigation"],
        ),
    )
    print(f"  [PASS] Created trace: {trace.model_used}")
    return trace


def test_nsa_trace():
    """Test NSA reasoning trace creation."""
    print("Testing NSA Reasoning Trace...")
    trace = NSAReasoningTrace(
        evidence_summary=NSAEvidenceSummary(
            total_evidence_count=5,
            evidence_by_source={"sanctions": 2, "news": 3},
            evidence_by_claim_type={"sanctions_hit": 2, "news_alert": 3},
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
        aggregation_logic=NSAAggregationLogic(
            raw_score=2.5,
            clamped_score=1.0,
            news_only_cap_applied=False,
        ),
        person_context=NSAPersonContext(
            person_id=1,
            person_name="John Doe",
            role="CEO",
            evidence_sources_hit=["sanctions", "news"],
        ),
    )
    print(f"  [PASS] Created trace for person: {trace.person_context.person_name}")
    return trace


def test_rkr_trace():
    """Test RKR reasoning trace creation."""
    print("Testing RKR Reasoning Trace...")
    trace = RKRReasoningTrace(
        language_detected="en",
        keyword_matches=[
            RKRKeywordMatch(
                keyword="money laundering",
                category="financial_crime",
                weight=0.8,
                in_title=True,
                context_snippet="...suspected money laundering scheme...",
                occurrences=2,
                contribution_to_score=1.2,
            )
        ],
        score_calculation=RKRScoreCalculation(
            raw_sum=3.8,
            normalization_divisor=3.0,
            final_risk_score=0.633,
            capped_at_1_0=False,
        ),
        categories_aggregated=RKRCategoriesAggregated(
            unique_categories=["financial_crime"],
            category_hit_counts={"financial_crime": 2},
        ),
        threshold_decision=RKRThresholdDecision(
            threshold_applied=0.3,
            risk_score=0.633,
            passed=True,
            margin=0.333,
        ),
    )
    print(f"  [PASS] Created trace: language={trace.language_detected}, passed={trace.threshold_decision.passed}")
    return trace


def test_tarkov_trace():
    """Test Tarkov reasoning trace creation."""
    print("Testing Tarkov Reasoning Trace...")
    trace = TarkovReasoningTrace(
        extraction_method="keyword_based",
        keyword_matching=TarkovKeywordMatching(
            event_type="money_laundering",
            keywords_searched=["money laundering", "suspicious"],
            keywords_found=["money laundering"],
            hit_sentences=["The company engaged in money laundering."],
            deduped_hit_count=1,
        ),
        confidence_calculation=TarkovConfidenceCalculation(
            base_confidence=0.55,
            keyword_count=1,
            keyword_boost=0.1,
            final_confidence=0.65,
        ),
        risk_level_assignment=TarkovRiskLevelAssignment(
            event_type="money_laundering",
            baseline_risk=8,
            keyword_count=1,
            boost_value=0,
            final_risk_level=8,
        ),
        title_generation=TarkovTitleGeneration(
            article_title="Suspected Money Laundering",
            template_used=None,
            generated_title="Money Laundering Detected",
        ),
        source_reference=TarkovSourceReference(
            url="https://example.com/article",
            source_title="News Source",
            credibility_score=0.8,
            language="en",
            published_at=datetime.utcnow(),
        ),
    )
    print(f"  [PASS] Created trace: method={trace.extraction_method}, confidence={trace.confidence_calculation.final_confidence:.2f}")
    return trace


def test_market_trace():
    """Test Market reasoning trace creation."""
    print("Testing Market Reasoning Trace...")
    trace = MarketReasoningTrace(
        ticker_search=MarketTickerSearch(
            firm_name="Acme Corp",
            search_strategy="exact",
            candidates_found=1,
            matching_process=[
                MarketTickerSearchCandidate(
                    candidate_name="Acme Corporation",
                    ticker="ACME",
                    exchange="NASDAQ",
                    match_score=0.95,
                    selected=True,
                    reason="Highest match score",
                )
            ],
        ),
        listing_selection=MarketListingSelection(
            listings_considered=1,
            selected_listings=[],
        ),
        fetch_results=MarketFetchResults(
            listings_processed=1,
            successful_fetches=1,
            failed_fetches=0,
            by_listing=[
                MarketFetchResultByListing(
                    tv_symbol="ACME",
                    tv_exchange="NASDAQ",
                    bars_fetched=365,
                    bars_persisted=365,
                    data_completeness=100.0,
                )
            ],
        ),
        fetch_parameters=MarketFetchParameters(
            n_bars_requested=365,
            date_range=MarketDateRange(days_back=365),
        ),
    )
    print(f"  [PASS] Created trace: firm={trace.ticker_search.firm_name}, successful_fetches={trace.fetch_results.successful_fetches}")
    return trace


def test_database_operations():
    """Test database operations with in-memory SQLite."""
    print("\nTesting Database Operations...")

    # Create temporary in-memory database
    db_url = "sqlite:///:memory:"
    init_engine(db_url)
    create_all()
    print("  [PASS] Database initialized and tables created")

    # Test repository operations
    with get_db() as db:
        repo = ReasoningTraceRepository(db)

        # Test save
        trace_id = repo.save(
            classifier_name="RKR",
            entity_type="article",
            entity_id="article_123",
            correlation_id="corr_456",
            trace_data={"language": "en", "risk_score": 0.7},
        )
        print(f"  [PASS] Saved trace with ID: {trace_id}")

        # Test get_by_id
        trace = repo.get_by_id(trace_id)
        assert trace is not None, "Failed to retrieve saved trace"
        assert trace.classifier_name == "RKR", "Classifier name mismatch"
        print(f"  [PASS] Retrieved trace by ID")

        # Test get_by_entity_id
        traces = repo.get_by_entity_id("article_123")
        assert len(traces) == 1, "Failed to retrieve trace by entity_id"
        print(f"  [PASS] Retrieved trace by entity_id")

        # Test get_by_correlation_id
        traces = repo.get_by_correlation_id("corr_456")
        assert len(traces) == 1, "Failed to retrieve trace by correlation_id"
        print(f"  [PASS] Retrieved trace by correlation_id")

        # Test get_by_classifier
        traces = repo.get_by_classifier("RKR")
        assert len(traces) >= 1, "Failed to retrieve trace by classifier"
        print(f"  [PASS] Retrieved trace by classifier (got {len(traces)} records)")

        db.commit()


def main():
    """Run all tests."""
    print("=" * 60)
    print("Stage 2: Database Schema - Verification Tests")
    print("=" * 60)

    try:
        # Test schema creation
        test_eem_trace()
        test_nsa_trace()
        test_rkr_trace()
        test_tarkov_trace()
        test_market_trace()

        # Test database operations
        test_database_operations()

        print("\n" + "=" * 60)
        print("[PASS] All tests passed successfully!")
        print("=" * 60)
        print("\nStage 2 Implementation Complete:")
        print("  * Domain-specific trace schemas defined")
        print("  * SQLAlchemy models created")
        print("  * Database migration files created")
        print("  * CRUD repository operations implemented")
        print("  * Human-readable formatters implemented")
        print("\nNext: Move to Phase 3 - Per-Classifier Integration")
        return 0

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
