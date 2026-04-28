"""Domain-specific reasoning trace schemas using Pydantic."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# EEM Reasoning Trace
# ============================================================================


class EEMSentimentCalculation(BaseModel):
    """Sentiment calculation breakdown for EEM."""

    base_sentiment: float
    event_type: str
    keyword_influences: list[str]
    final_sentiment: float


class EEMImpactScoring(BaseModel):
    """Impact scoring breakdown for EEM."""

    baseline_impact: float
    risk_level: int
    keyword_boost: float
    final_impact: float


class EEMSourceTierLogic(BaseModel):
    """Source tier assignment reasoning for EEM."""

    tier_assigned: str
    authority_indicators: list[str]
    reasoning: str


class EEMKeywordExtraction(BaseModel):
    """Keyword extraction details for EEM."""

    extracted_keywords: list[str]
    dedup_count: int
    top_6_keywords: list[str]


class EEMReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for EEM classifier."""

    model_config = ConfigDict(protected_namespaces=())

    model_used: str  # "llm" | "deterministic"
    fallback_reason: Optional[str] = None
    sentiment_calculation: EEMSentimentCalculation
    impact_scoring: EEMImpactScoring
    source_tier_logic: EEMSourceTierLogic
    keyword_extraction: EEMKeywordExtraction


# ============================================================================
# NSA Reasoning Trace
# ============================================================================


class NSAEvidenceSummary(BaseModel):
    """Summary of evidence aggregation for NSA."""

    total_evidence_count: int
    evidence_by_source: dict[str, int]  # {"sanctions": 2, "news": 3, ...}
    evidence_by_claim_type: dict[str, int]


class NSAScoringBreakdownItem(BaseModel):
    """Detailed breakdown of a single evidence contribution."""

    evidence_id: int
    source_kind: str
    claim_type: str
    claim_weight: float
    source_multiplier: float
    severity: float
    confidence: float
    official_bonus: float
    contribution_to_score: float


class NSAAggregationLogic(BaseModel):
    """Aggregation and clamping logic for NSA scoring."""

    raw_score: float
    clamped_score: float
    news_only_cap_applied: bool
    news_only_cap_value: Optional[float] = None


class NSAPersonContext(BaseModel):
    """Context about the person being scored."""

    person_id: int
    person_name: str
    role: Optional[str] = None
    evidence_sources_hit: list[str]


class NSAReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for NSA classifier."""

    evidence_summary: NSAEvidenceSummary
    scoring_breakdown: list[NSAScoringBreakdownItem]
    aggregation_logic: NSAAggregationLogic
    person_context: NSAPersonContext


# ============================================================================
# RKR Reasoning Trace
# ============================================================================


class RKRKeywordMatch(BaseModel):
    """Details of a single keyword match for RKR."""

    keyword: str
    category: str
    weight: float
    in_title: bool
    context_snippet: str
    occurrences: int
    contribution_to_score: float


class RKRScoreCalculation(BaseModel):
    """Score calculation breakdown for RKR."""

    raw_sum: float
    normalization_divisor: float
    final_risk_score: float
    capped_at_1_0: bool


class RKRCategoriesAggregated(BaseModel):
    """Category aggregation for RKR."""

    unique_categories: list[str]
    category_hit_counts: dict[str, int]


class RKRThresholdDecision(BaseModel):
    """Threshold decision logic for RKR."""

    threshold_applied: float
    risk_score: float
    passed: bool
    margin: float  # risk_score - threshold


class RKRReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for RKR classifier."""

    language_detected: str
    keyword_matches: list[RKRKeywordMatch]
    score_calculation: RKRScoreCalculation
    categories_aggregated: RKRCategoriesAggregated
    threshold_decision: RKRThresholdDecision


# ============================================================================
# Tarkov Reasoning Trace
# ============================================================================


class TarkovKeywordMatching(BaseModel):
    """Keyword matching details for Tarkov."""

    event_type: str
    keywords_searched: list[str]
    keywords_found: list[str]
    hit_sentences: list[str]
    deduped_hit_count: int


class TarkovConfidenceCalculation(BaseModel):
    """Confidence calculation breakdown for Tarkov."""

    base_confidence: float  # 0.55
    keyword_count: int
    keyword_boost: float  # 0.1 * min(4, len(unique_keywords_found))
    final_confidence: float


class TarkovRiskLevelAssignment(BaseModel):
    """Risk level assignment logic for Tarkov."""

    event_type: str
    baseline_risk: int
    keyword_count: int
    boost_value: int  # min(2, max(0, len(unique_keywords) - 1))
    final_risk_level: int


class TarkovTitleGeneration(BaseModel):
    """Title generation details for Tarkov."""

    article_title: str
    template_used: Optional[str] = None
    generated_title: str


class TarkovSourceReference(BaseModel):
    """Source reference details for Tarkov."""

    url: str
    source_title: str
    credibility_score: float
    language: str
    published_at: Optional[datetime] = None


class TarkovReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for Tarkov classifier."""

    extraction_method: str  # "keyword_based" | "llm_based"
    keyword_matching: TarkovKeywordMatching
    confidence_calculation: TarkovConfidenceCalculation
    risk_level_assignment: TarkovRiskLevelAssignment
    title_generation: TarkovTitleGeneration
    source_reference: TarkovSourceReference


# ============================================================================
# Market Reasoning Trace
# ============================================================================


class MarketTickerSearchCandidate(BaseModel):
    """A candidate in ticker search results."""

    candidate_name: str
    ticker: str
    exchange: str
    match_score: float
    selected: bool
    reason: str


class MarketTickerSearch(BaseModel):
    """Ticker search strategy and results for Market."""

    firm_name: str
    search_strategy: str  # "exact" | "fuzzy" | "partial"
    candidates_found: int
    matching_process: list[MarketTickerSearchCandidate]


class MarketSelectedListing(BaseModel):
    """A selected listing for data fetching."""

    tv_symbol: str
    tv_exchange: str
    ticker: str
    exchange: str


class MarketListingSelection(BaseModel):
    """Listing selection details for Market."""

    listings_considered: int
    selected_listings: list[MarketSelectedListing]


class MarketFetchResultByListing(BaseModel):
    """Fetch results for a single listing."""

    tv_symbol: str
    tv_exchange: str
    bars_fetched: int
    bars_persisted: int
    data_completeness: float  # %
    error: Optional[str] = None


class MarketFetchResults(BaseModel):
    """Overall fetch results aggregation for Market."""

    listings_processed: int
    successful_fetches: int
    failed_fetches: int
    by_listing: list[MarketFetchResultByListing]


class MarketDateRange(BaseModel):
    """Date range for fetch parameters."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    days_back: int


class MarketFetchParameters(BaseModel):
    """Fetch parameters used for Market data fetching."""

    n_bars_requested: int
    date_range: MarketDateRange


class MarketReasoningTrace(BaseModel):
    """Domain-specific reasoning trace for Market classifier."""

    ticker_search: MarketTickerSearch
    listing_selection: MarketListingSelection
    fetch_results: MarketFetchResults
    fetch_parameters: MarketFetchParameters


# ============================================================================
# Union type and storage model
# ============================================================================


ReasoningTraceData = Union[
    EEMReasoningTrace,
    NSAReasoningTrace,
    RKRReasoningTrace,
    TarkovReasoningTrace,
    MarketReasoningTrace,
]


class ReasoningTraceStorageModel(BaseModel):
    """Storage model for reasoning traces (database representation)."""

    classifier_name: str  # "EEM" | "NSA" | "RKR" | "Tarkov" | "Market"
    entity_type: str  # "event", "person", "article", etc.
    entity_id: str  # event_id, person_id, article_id, etc.
    correlation_id: Optional[str] = None  # links to parent event/article
    trace_data: dict[str, Any]  # domain-specific trace object (JSON-serializable)
    created_at: datetime = Field(default_factory=datetime.utcnow)
