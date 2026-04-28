from __future__ import annotations

from dataclasses import dataclass

from nsa.schemas.domain import PersonScoreInput
from reasoning.collectors.nsa_collector import NSATraceCollector
from reasoning.schemas import NSAReasoningTrace


@dataclass(frozen=True)
class PersonScoreResult:
    person_id: int
    person_risk_score: float
    analysis: str


CLAIM_WEIGHTS = {
    "warning_list_hit": 0.85,
    "sanctions_hit": 0.95,
    "ponzi_link": 0.8,
    "fraud_allegation": 0.45,
    "aml_investigation": 0.7,
}


SOURCE_MULTIPLIERS = {
    "warning_list": 1.0,
    "sanctions": 1.0,
    "registry": 0.85,
    "news": 0.6,
}

OFFICIAL_SOURCE_BONUS = {
    "warning_list": 0.05,
    "sanctions": 0.05,
}


def score_person(person: PersonScoreInput) -> tuple[PersonScoreResult, NSAReasoningTrace]:
    reasons: list[str] = []
    score = 0.0
    
    collector = NSATraceCollector(person.person_id, getattr(person, "person_name", "Unknown"), person_role=None)

    for item in person.evidence:
        contribution = (
            CLAIM_WEIGHTS.get(item.claim_type, 0.2)
            * SOURCE_MULTIPLIERS.get(item.source_kind, 0.5)
            * item.severity
            * item.confidence
        )
        official_bonus = OFFICIAL_SOURCE_BONUS.get(item.source_kind, 0.0) * item.severity * item.confidence
        total_contribution = contribution + official_bonus
        score += total_contribution
        
        # Record evidence item in trace collector
        collector.record_evidence_item(
            evidence_id=getattr(item, "id", 0),
            source_kind=item.source_kind,
            claim_type=item.claim_type,
            claim_weight=CLAIM_WEIGHTS.get(item.claim_type, 0.2),
            source_multiplier=SOURCE_MULTIPLIERS.get(item.source_kind, 0.5),
            severity=item.severity,
            confidence=item.confidence,
            official_bonus=official_bonus,
            contribution_to_score=total_contribution,
        )
        reasons.append(f"{item.source_kind}:{item.claim_type}")

    raw_score = score
    clamped_score = max(0.0, min(1.0, score))
    news_only_cap_applied = False
    news_only_cap_value = None
    
    if len(person.evidence) > 1 and all(item.source_kind == "news" for item in person.evidence):
        news_only_cap_applied = True
        news_only_cap_value = 0.85
        clamped_score = min(clamped_score, 0.85)
    
    collector.record_score_calculation(
        raw_score=raw_score,
        clamped_score=clamped_score,
        news_only_cap_applied=news_only_cap_applied,
        news_only_cap_value=news_only_cap_value,
    )

    analysis = "No adverse evidence found." if not reasons else f"Risk evidence: {', '.join(reasons)}"
    result = PersonScoreResult(person_id=person.person_id, person_risk_score=clamped_score, analysis=analysis)
    trace = collector.collect()
    return result, trace
