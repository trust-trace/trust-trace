"""Reasoning trace collector for EEM (Event Enrichment Module)."""

from __future__ import annotations

from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import EEMReasoningTrace, EEMSentimentCalculation, EEMImpactScoring, EEMSourceTierLogic, EEMKeywordExtraction


@TraceCollectorRegistry.register("EEM")
class EEMTraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during EEM event enrichment."""

    def __init__(self, event_id: str, firm_name: str):
        """Initialize collector for an event.
        
        Args:
            event_id: ID of the event being enriched
            firm_name: Name of the firm being analyzed
        """
        self.event_id = event_id
        self.firm_name = firm_name
        self.model_used: str | None = None
        self.fallback_reason: str | None = None
        self.sentiment_calculation: EEMSentimentCalculation | None = None
        self.impact_scoring: EEMImpactScoring | None = None
        self.source_tier_logic: EEMSourceTierLogic | None = None
        self.keyword_extraction: EEMKeywordExtraction | None = None

    def record_llm_success(self, fields, raw_response: str) -> None:
        """Record successful LLM analysis result.
        
        Args:
            fields: Parsed _EventFields from LLM response
            raw_response: Raw string response from LLM
        """
        self.model_used = "llm"
        
        # Extract calculation details from fields
        self.sentiment_calculation = EEMSentimentCalculation(
            base_sentiment=fields.sentiment,
            event_type="",  # Would be extracted from event context
            keyword_influences=[],  # Would be extracted from LLM response
            final_sentiment=fields.sentiment,
        )
        
        self.impact_scoring = EEMImpactScoring(
            baseline_impact=0.0,  # Would be calculated
            risk_level=0,  # Would be from event
            keyword_boost=0.0,  # Would be extracted
            final_impact=fields.impact,
        )
        
        self.source_tier_logic = EEMSourceTierLogic(
            tier_assigned=fields.source_tier,
            authority_indicators=[],  # Would be extracted from context
            reasoning="LLM analysis determined tier based on source authority and content.",
        )
        
        self.keyword_extraction = EEMKeywordExtraction(
            extracted_keywords=fields.keywords,
            dedup_count=len(set(fields.keywords)),
            top_6_keywords=fields.keywords[:6],
        )

    def record_fallback(self, exception: Exception) -> None:
        """Record fallback to deterministic analysis.
        
        Args:
            exception: Exception that triggered fallback
        """
        self.model_used = "deterministic"
        self.fallback_reason = str(exception)

    def record_deterministic_result(self, fields, event_type: str = "", keyword_influences: list[str] = None) -> None:
        """Record deterministic analysis result.
        
        Args:
            fields: _EventFields from deterministic analysis
            event_type: Type of the event
            keyword_influences: Keywords that influenced the sentiment
        """
        self.model_used = "deterministic"
        
        if keyword_influences is None:
            keyword_influences = []
        
        self.sentiment_calculation = EEMSentimentCalculation(
            base_sentiment=fields.sentiment,
            event_type=event_type,
            keyword_influences=keyword_influences,
            final_sentiment=fields.sentiment,
        )
        
        self.impact_scoring = EEMImpactScoring(
            baseline_impact=0.0,
            risk_level=0,
            keyword_boost=0.0,
            final_impact=fields.impact,
        )
        
        self.source_tier_logic = EEMSourceTierLogic(
            tier_assigned=fields.source_tier,
            authority_indicators=[],
            reasoning="Deterministic analysis assigned tier based on keyword matching.",
        )
        
        self.keyword_extraction = EEMKeywordExtraction(
            extracted_keywords=fields.keywords,
            dedup_count=len(set(fields.keywords)),
            top_6_keywords=fields.keywords[:6],
        )

    def collect(self) -> EEMReasoningTrace:
        """Collect and return the complete reasoning trace."""
        if not self.model_used:
            raise ValueError("Must call record_llm_success, record_fallback, or record_deterministic_result first")
        
        return EEMReasoningTrace(
            model_used=self.model_used,
            fallback_reason=self.fallback_reason,
            sentiment_calculation=self.sentiment_calculation or EEMSentimentCalculation(
                base_sentiment=0.0,
                event_type="",
                keyword_influences=[],
                final_sentiment=0.0,
            ),
            impact_scoring=self.impact_scoring or EEMImpactScoring(
                baseline_impact=0.0,
                risk_level=0,
                keyword_boost=0.0,
                final_impact=0.0,
            ),
            source_tier_logic=self.source_tier_logic or EEMSourceTierLogic(
                tier_assigned="tier-2",
                authority_indicators=[],
                reasoning="",
            ),
            keyword_extraction=self.keyword_extraction or EEMKeywordExtraction(
                extracted_keywords=[],
                dedup_count=0,
                top_6_keywords=[],
            ),
        )
