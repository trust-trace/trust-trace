"""Reasoning trace collector for NSA (Non-Sanctioned Analysis)."""

from __future__ import annotations

from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import (
    NSAReasoningTrace,
    NSAEvidenceSummary,
    NSAScoringBreakdownItem,
    NSAAggregationLogic,
    NSAPersonContext,
)


@TraceCollectorRegistry.register("NSA")
class NSATraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during NSA person/company scoring."""

    def __init__(self, person_id: int, person_name: str, person_role: str | None = None):
        """Initialize collector for a person scoring.
        
        Args:
            person_id: ID of the person being scored
            person_name: Name of the person
            person_role: Optional role of the person
        """
        self.person_id = person_id
        self.person_name = person_name
        self.person_role = person_role
        
        self.evidence_items: list[NSAScoringBreakdownItem] = []
        self.evidence_by_source: dict[str, int] = {}
        self.evidence_by_claim_type: dict[str, int] = {}
        self.evidence_sources_hit: set[str] = set()
        
        self.raw_score: float = 0.0
        self.clamped_score: float = 0.0
        self.news_only_cap_applied: bool = False
        self.news_only_cap_value: float | None = None

    def record_evidence_item(
        self,
        evidence_id: int,
        source_kind: str,
        claim_type: str,
        claim_weight: float,
        source_multiplier: float,
        severity: float,
        confidence: float,
        official_bonus: float,
        contribution_to_score: float,
    ) -> None:
        """Record analysis of a single evidence item.
        
        Args:
            evidence_id: ID of the evidence
            source_kind: Type of source (sanctions, warning_list, news, etc.)
            claim_type: Type of claim
            claim_weight: Weight applied to this claim
            source_multiplier: Multiplier based on source type
            severity: Severity score of the evidence
            confidence: Confidence in the evidence
            official_bonus: Official source bonus applied
            contribution_to_score: How much this evidence contributed to final score
        """
        item = NSAScoringBreakdownItem(
            evidence_id=evidence_id,
            source_kind=source_kind,
            claim_type=claim_type,
            claim_weight=claim_weight,
            source_multiplier=source_multiplier,
            severity=severity,
            confidence=confidence,
            official_bonus=official_bonus,
            contribution_to_score=contribution_to_score,
        )
        self.evidence_items.append(item)
        
        # Track evidence aggregation
        self.evidence_by_source[source_kind] = self.evidence_by_source.get(source_kind, 0) + 1
        self.evidence_by_claim_type[claim_type] = self.evidence_by_claim_type.get(claim_type, 0) + 1
        self.evidence_sources_hit.add(source_kind)

    def record_score_calculation(
        self,
        raw_score: float,
        clamped_score: float,
        news_only_cap_applied: bool = False,
        news_only_cap_value: float | None = None,
    ) -> None:
        """Record score aggregation and clamping logic.
        
        Args:
            raw_score: Raw calculated score before clamping
            clamped_score: Final score after clamping to [0, 1]
            news_only_cap_applied: Whether news-only cap was applied
            news_only_cap_value: Value of the news-only cap if applied
        """
        self.raw_score = raw_score
        self.clamped_score = clamped_score
        self.news_only_cap_applied = news_only_cap_applied
        self.news_only_cap_value = news_only_cap_value

    def collect(self) -> NSAReasoningTrace:
        """Collect and return the complete reasoning trace."""
        evidence_summary = NSAEvidenceSummary(
            total_evidence_count=len(self.evidence_items),
            evidence_by_source=self.evidence_by_source,
            evidence_by_claim_type=self.evidence_by_claim_type,
        )
        
        person_context = NSAPersonContext(
            person_id=self.person_id,
            person_name=self.person_name,
            role=self.person_role,
            evidence_sources_hit=sorted(self.evidence_sources_hit),
        )
        
        aggregation_logic = NSAAggregationLogic(
            raw_score=self.raw_score,
            clamped_score=self.clamped_score,
            news_only_cap_applied=self.news_only_cap_applied,
            news_only_cap_value=self.news_only_cap_value,
        )
        
        return NSAReasoningTrace(
            evidence_summary=evidence_summary,
            scoring_breakdown=self.evidence_items,
            aggregation_logic=aggregation_logic,
            person_context=person_context,
        )
