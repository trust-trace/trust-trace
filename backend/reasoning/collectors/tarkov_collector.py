"""Reasoning trace collector for Tarkov (Event Extraction)."""

from __future__ import annotations

from datetime import datetime
from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import (
    TarkovReasoningTrace,
    TarkovKeywordMatching,
    TarkovConfidenceCalculation,
    TarkovRiskLevelAssignment,
    TarkovTitleGeneration,
    TarkovSourceReference,
)


@TraceCollectorRegistry.register("Tarkov")
class TarkovTraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during Tarkov event extraction."""

    def __init__(self, event_type: str, article_id: str | None = None):
        """Initialize collector for event extraction.
        
        Args:
            event_type: Type of event being extracted (money_laundering, fraud, etc.)
            article_id: Optional ID of the article being processed
        """
        self.event_type = event_type
        self.article_id = article_id
        
        self.extraction_method: str | None = None
        self.keyword_matching: TarkovKeywordMatching | None = None
        self.confidence_calculation: TarkovConfidenceCalculation | None = None
        self.risk_level_assignment: TarkovRiskLevelAssignment | None = None
        self.title_generation: TarkovTitleGeneration | None = None
        self.source_reference: TarkovSourceReference | None = None

    def record_keyword_extraction(
        self,
        keywords_searched: list[str],
        keywords_found: list[str],
        hit_sentences: list[str] | None = None,
    ) -> None:
        """Record keyword-based extraction results.
        
        Args:
            keywords_searched: List of keywords searched for this event type
            keywords_found: Subset of keywords_searched that were actually found
            hit_sentences: Optional list of sentences containing keyword hits
        """
        self.extraction_method = "keyword_based"
        deduped_keywords = list(dict.fromkeys(keywords_found))
        
        self.keyword_matching = TarkovKeywordMatching(
            event_type=self.event_type,
            keywords_searched=keywords_searched,
            keywords_found=keywords_found,
            hit_sentences=hit_sentences or [],
            deduped_hit_count=len(deduped_keywords),
        )

    def record_llm_extraction(self, event_type: str) -> None:
        """Record LLM-based extraction.
        
        Args:
            event_type: Event type determined by LLM
        """
        self.extraction_method = "llm_based"
        self.keyword_matching = TarkovKeywordMatching(
            event_type=event_type,
            keywords_searched=[],
            keywords_found=[],
            hit_sentences=[],
            deduped_hit_count=0,
        )

    def record_confidence_calculation(
        self,
        base_confidence: float = 0.55,
        keyword_count: int = 0,
        keyword_boost: float = 0.0,
        final_confidence: float | None = None,
    ) -> None:
        """Record confidence score calculation.
        
        Args:
            base_confidence: Base confidence value (typically 0.55)
            keyword_count: Number of unique keywords found
            keyword_boost: Boost applied for keyword matches (0.1 * min(4, keyword_count))
            final_confidence: Final confidence score (base + boost if not provided)
        """
        calculated_final = final_confidence if final_confidence is not None else (base_confidence + keyword_boost)
        
        self.confidence_calculation = TarkovConfidenceCalculation(
            base_confidence=base_confidence,
            keyword_count=keyword_count,
            keyword_boost=keyword_boost,
            final_confidence=calculated_final,
        )

    def record_risk_level(
        self,
        baseline_risk: int,
        keyword_count: int = 0,
        boost_value: int = 0,
        final_risk_level: int | None = None,
    ) -> None:
        """Record risk level assignment logic.
        
        Args:
            baseline_risk: Base risk level for this event type
            keyword_count: Number of keywords found
            boost_value: Boost applied (min(2, max(0, keyword_count - 1)))
            final_risk_level: Final risk level (baseline + boost if not provided)
        """
        calculated_final = final_risk_level if final_risk_level is not None else (baseline_risk + boost_value)
        calculated_final = max(1, min(10, calculated_final))  # Clamp to [1, 10]
        
        self.risk_level_assignment = TarkovRiskLevelAssignment(
            event_type=self.event_type,
            baseline_risk=baseline_risk,
            keyword_count=keyword_count,
            boost_value=boost_value,
            final_risk_level=calculated_final,
        )

    def record_title_generation(
        self,
        article_title: str,
        generated_title: str,
        template_used: str | None = None,
    ) -> None:
        """Record title generation details.
        
        Args:
            article_title: Original article title
            generated_title: Generated event title
            template_used: Optional template that was used
        """
        self.title_generation = TarkovTitleGeneration(
            article_title=article_title,
            template_used=template_used,
            generated_title=generated_title,
        )

    def record_source_reference(
        self,
        url: str,
        source_title: str,
        credibility_score: float,
        language: str,
        published_at: datetime | None = None,
    ) -> None:
        """Record source article reference information.
        
        Args:
            url: URL of the source article
            source_title: Title of the source
            credibility_score: Credibility/reliability score
            language: Language of the article
            published_at: Publication date/time
        """
        self.source_reference = TarkovSourceReference(
            url=url,
            source_title=source_title,
            credibility_score=credibility_score,
            language=language,
            published_at=published_at,
        )

    def collect(self) -> TarkovReasoningTrace:
        """Collect and return the complete reasoning trace."""
        return TarkovReasoningTrace(
            extraction_method=self.extraction_method or "keyword_based",
            keyword_matching=self.keyword_matching or TarkovKeywordMatching(
                event_type=self.event_type,
                keywords_searched=[],
                keywords_found=[],
                hit_sentences=[],
                deduped_hit_count=0,
            ),
            confidence_calculation=self.confidence_calculation or TarkovConfidenceCalculation(
                base_confidence=0.55,
                keyword_count=0,
                keyword_boost=0.0,
                final_confidence=0.55,
            ),
            risk_level_assignment=self.risk_level_assignment or TarkovRiskLevelAssignment(
                event_type=self.event_type,
                baseline_risk=5,
                keyword_count=0,
                boost_value=0,
                final_risk_level=5,
            ),
            title_generation=self.title_generation or TarkovTitleGeneration(
                article_title="",
                template_used=None,
                generated_title="",
            ),
            source_reference=self.source_reference or TarkovSourceReference(
                url="",
                source_title="",
                credibility_score=0.5,
                language="en",
                published_at=None,
            ),
        )
