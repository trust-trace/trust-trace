from nsa.schemas.domain import PersonEvidence, PersonScoreInput
from nsa.scoring.rules import score_person


def test_warning_list_hit_produces_high_risk() -> None:
    person = PersonScoreInput(
        person_id=10,
        person_name="John Smith",
        role="CEO",
        evidence=(
            PersonEvidence(
                source_kind="warning_list",
                source_url="https://example.test/warnings/10",
                title="Public warning",
                excerpt="John Smith appears in warning list",
                severity=0.95,
                confidence=0.95,
                claim_type="warning_list_hit",
            ),
        ),
    )

    result = score_person(person)

    assert result.person_risk_score >= 0.8
    assert result.analysis == "Risk evidence: warning_list:warning_list_hit"


def test_multiple_medium_news_hits_are_capped() -> None:
    person = PersonScoreInput(
        person_id=11,
        person_name="Jane Doe",
        evidence=tuple(
            PersonEvidence(
                source_kind="news",
                source_url=f"https://example.test/news/{idx}",
                title="Fraud article",
                excerpt="Person linked to fraud allegations",
                severity=0.5,
                confidence=0.7,
                claim_type="fraud_allegation",
            )
            for idx in range(5)
        ),
    )

    result = score_person(person)

    assert 0.0 <= result.person_risk_score <= 0.85


def test_multiple_official_hits_are_not_capped_down() -> None:
    person = PersonScoreInput(
        person_id=13,
        person_name="Official Corroboration",
        evidence=(
            PersonEvidence(
                source_kind="warning_list",
                source_url="https://example.test/warnings/13",
                title="Warning list hit",
                excerpt="Person appears in warning list",
                severity=0.95,
                confidence=0.95,
                claim_type="warning_list_hit",
            ),
            PersonEvidence(
                source_kind="sanctions",
                source_url="https://example.test/sanctions/13",
                title="Sanctions hit",
                excerpt="Person appears in sanctions list",
                severity=0.9,
                confidence=0.9,
                claim_type="sanctions_hit",
            ),
        ),
    )

    result = score_person(person)

    assert result.person_risk_score > 0.85


def test_no_evidence_returns_zero_and_default_analysis() -> None:
    person = PersonScoreInput(person_id=12, person_name="No Evidence", evidence=())

    result = score_person(person)

    assert result.person_id == 12
    assert result.person_risk_score == 0.0
    assert result.analysis == "No adverse evidence found."
