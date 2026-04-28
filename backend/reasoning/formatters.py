"""Human-readable formatters for reasoning traces."""

from __future__ import annotations

import json
from typing import Any

from reasoning.schemas import (
    EEMReasoningTrace,
    MarketReasoningTrace,
    NSAReasoningTrace,
    RKRReasoningTrace,
    ReasoningTraceData,
    TarkovReasoningTrace,
)


def format_trace_compact(trace: ReasoningTraceData) -> str:
    """Format a reasoning trace as a single-line summary.

    Args:
        trace: The reasoning trace to format

    Returns:
        A compact string representation of the trace.
    """
    if isinstance(trace, EEMReasoningTrace):
        return (
            f"EEM Trace: model={trace.model_used}, "
            f"sentiment={trace.sentiment_calculation.final_sentiment:.2f}, "
            f"impact={trace.impact_scoring.final_impact:.2f}, "
            f"tier={trace.source_tier_logic.tier_assigned}"
        )
    elif isinstance(trace, NSAReasoningTrace):
        return (
            f"NSA Trace: person={trace.person_context.person_name}, "
            f"evidence_count={trace.evidence_summary.total_evidence_count}, "
            f"final_score={trace.aggregation_logic.clamped_score:.2f}"
        )
    elif isinstance(trace, RKRReasoningTrace):
        return (
            f"RKR Trace: language={trace.language_detected}, "
            f"matches={len(trace.keyword_matches)}, "
            f"risk_score={trace.score_calculation.final_risk_score:.2f}, "
            f"passed={trace.threshold_decision.passed}"
        )
    elif isinstance(trace, TarkovReasoningTrace):
        return (
            f"Tarkov Trace: method={trace.extraction_method}, "
            f"event_type={trace.keyword_matching.event_type}, "
            f"confidence={trace.confidence_calculation.final_confidence:.2f}, "
            f"risk_level={trace.risk_level_assignment.final_risk_level}"
        )
    elif isinstance(trace, MarketReasoningTrace):
        return (
            f"Market Trace: firm={trace.ticker_search.firm_name}, "
            f"strategy={trace.ticker_search.search_strategy}, "
            f"candidates={trace.ticker_search.candidates_found}, "
            f"successful_fetches={trace.fetch_results.successful_fetches}"
        )
    else:
        return f"Unknown trace type: {type(trace).__name__}"


def format_trace_pretty(trace: ReasoningTraceData, indent: int = 2) -> str:
    """Format a reasoning trace as pretty-printed JSON.

    Args:
        trace: The reasoning trace to format
        indent: Number of spaces for indentation

    Returns:
        A pretty-printed JSON string representation of the trace.
    """
    trace_dict = trace.model_dump()
    return json.dumps(trace_dict, ensure_ascii=False, indent=indent, default=str)


def format_trace_detailed(trace: ReasoningTraceData) -> str:
    """Format a reasoning trace with detailed human-readable explanation.

    Args:
        trace: The reasoning trace to format

    Returns:
        A multi-line detailed explanation of the trace.
    """
    lines = []

    if isinstance(trace, EEMReasoningTrace):
        lines.append("=== EEM Reasoning Trace ===")
        lines.append(f"Model Used: {trace.model_used}")
        if trace.fallback_reason:
            lines.append(f"Fallback Reason: {trace.fallback_reason}")

        lines.append("\n--- Sentiment Calculation ---")
        sc = trace.sentiment_calculation
        lines.append(f"  Base Sentiment: {sc.base_sentiment:.2f}")
        lines.append(f"  Event Type: {sc.event_type}")
        lines.append(f"  Keyword Influences: {', '.join(sc.keyword_influences)}")
        lines.append(f"  Final Sentiment: {sc.final_sentiment:.2f}")

        lines.append("\n--- Impact Scoring ---")
        i = trace.impact_scoring
        lines.append(f"  Baseline Impact: {i.baseline_impact:.2f}")
        lines.append(f"  Risk Level: {i.risk_level}")
        lines.append(f"  Keyword Boost: {i.keyword_boost:.2f}")
        lines.append(f"  Final Impact: {i.final_impact:.2f}")

        lines.append("\n--- Source Tier Logic ---")
        st = trace.source_tier_logic
        lines.append(f"  Tier Assigned: {st.tier_assigned}")
        lines.append(f"  Authority Indicators: {', '.join(st.authority_indicators)}")
        lines.append(f"  Reasoning: {st.reasoning}")

        lines.append("\n--- Keyword Extraction ---")
        ke = trace.keyword_extraction
        lines.append(f"  Extracted Keywords: {', '.join(ke.extracted_keywords)}")
        lines.append(f"  Dedup Count: {ke.dedup_count}")
        lines.append(f"  Top 6: {', '.join(ke.top_6_keywords)}")

    elif isinstance(trace, NSAReasoningTrace):
        lines.append("=== NSA Reasoning Trace ===")

        lines.append("\n--- Person Context ---")
        pc = trace.person_context
        lines.append(f"  Person ID: {pc.person_id}")
        lines.append(f"  Name: {pc.person_name}")
        lines.append(f"  Role: {pc.role or 'N/A'}")
        lines.append(f"  Evidence Sources: {', '.join(pc.evidence_sources_hit)}")

        lines.append("\n--- Evidence Summary ---")
        es = trace.evidence_summary
        lines.append(f"  Total Evidence Count: {es.total_evidence_count}")
        lines.append("  Evidence by Source:")
        for source, count in es.evidence_by_source.items():
            lines.append(f"    {source}: {count}")
        lines.append("  Evidence by Claim Type:")
        for claim_type, count in es.evidence_by_claim_type.items():
            lines.append(f"    {claim_type}: {count}")

        lines.append("\n--- Aggregation Logic ---")
        agg = trace.aggregation_logic
        lines.append(f"  Raw Score: {agg.raw_score:.4f}")
        lines.append(f"  Clamped Score: {agg.clamped_score:.4f}")
        lines.append(f"  News-Only Cap Applied: {agg.news_only_cap_applied}")
        if agg.news_only_cap_value is not None:
            lines.append(f"  News-Only Cap Value: {agg.news_only_cap_value:.4f}")

        lines.append("\n--- Scoring Breakdown ---")
        for item in trace.scoring_breakdown[:3]:  # Show first 3 for brevity
            lines.append(f"  Evidence {item.evidence_id}:")
            lines.append(f"    Source: {item.source_kind} ({item.source_multiplier}x)")
            lines.append(f"    Claim: {item.claim_type} (weight: {item.claim_weight:.2f})")
            lines.append(f"    Contribution: {item.contribution_to_score:.4f}")

        if len(trace.scoring_breakdown) > 3:
            lines.append(f"  ... and {len(trace.scoring_breakdown) - 3} more items")

    elif isinstance(trace, RKRReasoningTrace):
        lines.append("=== RKR Reasoning Trace ===")
        lines.append(f"Language Detected: {trace.language_detected}")

        lines.append("\n--- Score Calculation ---")
        sc = trace.score_calculation
        lines.append(f"  Raw Sum: {sc.raw_sum:.2f}")
        lines.append(f"  Normalization Divisor: {sc.normalization_divisor}")
        lines.append(f"  Final Risk Score: {sc.final_risk_score:.4f}")
        lines.append(f"  Capped at 1.0: {sc.capped_at_1_0}")

        lines.append("\n--- Threshold Decision ---")
        td = trace.threshold_decision
        lines.append(f"  Threshold: {td.threshold_applied:.2f}")
        lines.append(f"  Risk Score: {td.risk_score:.4f}")
        lines.append(f"  Passed: {td.passed}")
        lines.append(f"  Margin: {td.margin:.4f}")

        lines.append("\n--- Categories Aggregated ---")
        ca = trace.categories_aggregated
        lines.append(f"  Unique Categories: {', '.join(ca.unique_categories)}")
        for cat, count in ca.category_hit_counts.items():
            lines.append(f"    {cat}: {count}")

        lines.append("\n--- Top Keyword Matches ---")
        for match in trace.keyword_matches[:5]:  # Show first 5
            lines.append(f"  '{match.keyword}' (category: {match.category})")
            lines.append(f"    Weight: {match.weight:.2f}, In Title: {match.in_title}")
            lines.append(f"    Occurrences: {match.occurrences}")
            lines.append(f"    Contribution: {match.contribution_to_score:.2f}")

        if len(trace.keyword_matches) > 5:
            lines.append(f"  ... and {len(trace.keyword_matches) - 5} more matches")

    elif isinstance(trace, TarkovReasoningTrace):
        lines.append("=== Tarkov Reasoning Trace ===")
        lines.append(f"Extraction Method: {trace.extraction_method}")

        lines.append("\n--- Confidence Calculation ---")
        cc = trace.confidence_calculation
        lines.append(f"  Base Confidence: {cc.base_confidence:.2f}")
        lines.append(f"  Keyword Count: {cc.keyword_count}")
        lines.append(f"  Keyword Boost: {cc.keyword_boost:.2f}")
        lines.append(f"  Final Confidence: {cc.final_confidence:.4f}")

        lines.append("\n--- Risk Level Assignment ---")
        rla = trace.risk_level_assignment
        lines.append(f"  Event Type: {rla.event_type}")
        lines.append(f"  Baseline Risk: {rla.baseline_risk}")
        lines.append(f"  Keyword Count: {rla.keyword_count}")
        lines.append(f"  Boost Value: {rla.boost_value}")
        lines.append(f"  Final Risk Level: {rla.final_risk_level}")

        lines.append("\n--- Keyword Matching ---")
        km = trace.keyword_matching
        lines.append(f"  Keywords Found: {', '.join(km.keywords_found)}")
        lines.append(f"  Hit Sentences: {len(km.hit_sentences)}")
        lines.append(f"  Deduped Hit Count: {km.deduped_hit_count}")

        lines.append("\n--- Source Reference ---")
        sr = trace.source_reference
        lines.append(f"  URL: {sr.url}")
        lines.append(f"  Title: {sr.source_title}")
        lines.append(f"  Language: {sr.language}")
        lines.append(f"  Published: {sr.published_at}")

    elif isinstance(trace, MarketReasoningTrace):
        lines.append("=== Market Reasoning Trace ===")

        lines.append("\n--- Ticker Search ---")
        ts = trace.ticker_search
        lines.append(f"  Firm Name: {ts.firm_name}")
        lines.append(f"  Search Strategy: {ts.search_strategy}")
        lines.append(f"  Candidates Found: {ts.candidates_found}")

        for candidate in ts.matching_process:
            lines.append(f"    {candidate.candidate_name} ({candidate.ticker})")
            lines.append(f"      Score: {candidate.match_score:.2f}, Selected: {candidate.selected}")

        lines.append("\n--- Listing Selection ---")
        ls = trace.listing_selection
        lines.append(f"  Listings Considered: {ls.listings_considered}")
        lines.append(f"  Selected: {len(ls.selected_listings)}")

        lines.append("\n--- Fetch Results ---")
        fr = trace.fetch_results
        lines.append(f"  Listings Processed: {fr.listings_processed}")
        lines.append(f"  Successful: {fr.successful_fetches}")
        lines.append(f"  Failed: {fr.failed_fetches}")

        for result in fr.by_listing:
            lines.append(f"    {result.tv_symbol}:")
            lines.append(f"      Bars: {result.bars_fetched} fetched, {result.bars_persisted} persisted")
            lines.append(f"      Completeness: {result.data_completeness:.1f}%")
            if result.error:
                lines.append(f"      Error: {result.error}")

    else:
        lines.append(f"Unknown trace type: {type(trace).__name__}")

    return "\n".join(lines)


def format_trace_csv_header(trace_type: str) -> str:
    """Generate CSV header for a specific trace type.

    Args:
        trace_type: Type of trace (EEM, NSA, RKR, Tarkov, Market)

    Returns:
        CSV header string.
    """
    headers = {
        "EEM": "timestamp,classifier,entity_id,model_used,final_sentiment,final_impact,source_tier,keyword_count",
        "NSA": "timestamp,classifier,entity_id,person_id,person_name,total_evidence,clamped_score",
        "RKR": "timestamp,classifier,entity_id,language,keyword_matches,final_risk_score,passed_threshold",
        "Tarkov": "timestamp,classifier,entity_id,extraction_method,event_type,final_confidence,final_risk_level",
        "Market": "timestamp,classifier,entity_id,firm_name,search_strategy,candidates_found,successful_fetches",
    }
    return headers.get(trace_type, "timestamp,classifier,entity_id,data")
