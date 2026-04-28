"""Reasoning trace collector for RKR (Risk Keyword Recognition)."""

from __future__ import annotations

from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import (
    RKRReasoningTrace,
    RKRKeywordMatch,
    RKRScoreCalculation,
    RKRCategoriesAggregated,
    RKRThresholdDecision,
)


@TraceCollectorRegistry.register("RKR")
class RKRTraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during RKR article scanning."""

    def __init__(self, article_id: str | None = None):
        """Initialize collector for article risk scoring.
        
        Args:
            article_id: Optional ID of the article being scanned
        """
        self.article_id = article_id
        self.language_detected: str | None = None
        self.keyword_matches: list[RKRKeywordMatch] = []
        self.categories_hit: set[str] = set()
        
        self.raw_sum: float = 0.0
        self.normalization_divisor: float = 3.0
        self.final_risk_score: float = 0.0
        self.capped_at_1_0: bool = False
        
        self.threshold_applied: float = 0.3
        self.passed_threshold: bool = False

    def record_language(self, language: str) -> None:
        """Record detected language of article.
        
        Args:
            language: Language code or name (e.g., "en", "pl")
        """
        self.language_detected = language

    def record_keyword_match(
        self,
        keyword: str,
        category: str,
        weight: float,
        in_title: bool,
        context_snippet: str,
        occurrences: int = 1,
        title_multiplier: float = 1.5,
    ) -> None:
        """Record a single keyword match.
        
        Args:
            keyword: The keyword that was matched
            category: Category this keyword belongs to
            weight: Base weight of the keyword
            in_title: Whether keyword appeared in title
            context_snippet: Snippet of text around keyword (50-100 chars)
            occurrences: Number of times keyword was found
            title_multiplier: Multiplier to apply if in_title (default 1.5)
        """
        contribution = weight * (title_multiplier if in_title else 1.0)
        
        match = RKRKeywordMatch(
            keyword=keyword,
            category=category,
            weight=weight,
            in_title=in_title,
            context_snippet=context_snippet,
            occurrences=occurrences,
            contribution_to_score=contribution,
        )
        self.keyword_matches.append(match)
        self.categories_hit.add(category)

    def record_score_calculation(
        self,
        raw_sum: float,
        normalization_divisor: float = 3.0,
        final_risk_score: float | None = None,
        capped_at_1_0: bool = False,
    ) -> None:
        """Record score calculation details.
        
        Args:
            raw_sum: Sum of all keyword contributions before normalization
            normalization_divisor: Divisor used for normalization
            final_risk_score: Final calculated risk score (raw_sum / divisor if not provided)
            capped_at_1_0: Whether final score was capped at 1.0
        """
        self.raw_sum = raw_sum
        self.normalization_divisor = normalization_divisor
        self.final_risk_score = final_risk_score if final_risk_score is not None else (raw_sum / normalization_divisor)
        self.capped_at_1_0 = capped_at_1_0

    def record_threshold_decision(
        self,
        threshold: float,
        passed: bool,
    ) -> None:
        """Record threshold comparison decision.
        
        Args:
            threshold: Threshold value used for comparison
            passed: Whether risk_score >= threshold
        """
        self.threshold_applied = threshold
        self.passed_threshold = passed

    def collect(self) -> RKRReasoningTrace:
        """Collect and return the complete reasoning trace."""
        category_hit_counts = {}
        for category in self.categories_hit:
            category_hit_counts[category] = sum(
                1 for match in self.keyword_matches if match.category == category
            )
        
        score_calculation = RKRScoreCalculation(
            raw_sum=self.raw_sum,
            normalization_divisor=self.normalization_divisor,
            final_risk_score=self.final_risk_score,
            capped_at_1_0=self.capped_at_1_0,
        )
        
        categories_aggregated = RKRCategoriesAggregated(
            unique_categories=sorted(self.categories_hit),
            category_hit_counts=category_hit_counts,
        )
        
        threshold_decision = RKRThresholdDecision(
            threshold_applied=self.threshold_applied,
            risk_score=self.final_risk_score,
            passed=self.passed_threshold,
            margin=self.final_risk_score - self.threshold_applied,
        )
        
        return RKRReasoningTrace(
            language_detected=self.language_detected or "unknown",
            keyword_matches=self.keyword_matches,
            score_calculation=score_calculation,
            categories_aggregated=categories_aggregated,
            threshold_decision=threshold_decision,
        )
