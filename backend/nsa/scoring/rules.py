from __future__ import annotations

from dataclasses import dataclass

from nsa.schemas.domain import PersonScoreInput


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


def score_person(person: PersonScoreInput) -> PersonScoreResult:
    reasons: list[str] = []
    score = 0.0

    for item in person.evidence:
        score += (
            CLAIM_WEIGHTS.get(item.claim_type, 0.2)
            * SOURCE_MULTIPLIERS.get(item.source_kind, 0.5)
            * item.severity
            * item.confidence
        )
        score += OFFICIAL_SOURCE_BONUS.get(item.source_kind, 0.0) * item.severity * item.confidence
        reasons.append(f"{item.source_kind}:{item.claim_type}")

    score = max(0.0, min(1.0, score))
    if len(person.evidence) > 1 and all(item.source_kind == "news" for item in person.evidence):
        score = min(score, 0.85)

    analysis = "No adverse evidence found." if not reasons else f"Risk evidence: {', '.join(reasons)}"
    return PersonScoreResult(person_id=person.person_id, person_risk_score=score, analysis=analysis)
