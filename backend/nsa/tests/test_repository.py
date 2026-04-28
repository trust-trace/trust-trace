from __future__ import annotations

from datetime import datetime
from nsa.database.models import NsaCompanyAssessment, NsaEvidence, NsaPersonAssessment
from nsa.database.repository import NsaRepository


def test_load_company_context_returns_firm_people_events_sources(db_session) -> None:
    repo = NsaRepository(db_session)

    context = repo.load_company_context(1)

    assert context.firm.id == 1
    assert context.firm.full_name == "Acme Sp. z o.o."
    assert len(context.people) == 1
    assert context.people[0].name == "Jane Doe"
    assert len(context.events) == 1
    assert len(context.sources) == 1


def test_load_company_context_handles_events_without_sources(db_session) -> None:
    from tarkov.database.models import Event, Firm

    firm = Firm(full_name="No Source Ltd", country="PL")
    db_session.add(firm)
    db_session.flush()

    event = Event(
        firm_id=firm.id,
        title="Source-less event",
        event_type="news",
        event_category="classical",
        risk_level=2,
        occurred_at=datetime(2024, 1, 2),
    )
    db_session.add(event)
    db_session.commit()

    repo = NsaRepository(db_session)

    context = repo.load_company_context(firm.id)

    assert len(context.events) == 1
    assert context.sources == []


def test_save_assessment_persists_assessment_rows(db_session) -> None:
    repo = NsaRepository(db_session)

    result = repo.save_assessment(
        firm_id=1,
        correlation_id="cid-1",
        company_risk_score=0.7,
        people=[
            {
                "person_id": 1,
                "person_risk_score": 0.8,
                "analysis": "high risk",
                "evidence": [
                    {
                        "source_kind": "news",
                        "source_url": "https://example.com/article",
                        "title": "Example article",
                        "excerpt": "Mentioned in investigation",
                        "severity": 0.9,
                    }
                ],
            }
        ],
    )

    assert result.company_assessment.id is not None
    assert result.company_assessment.firm_id == 1
    assert result.company_assessment.company_risk_score == 0.7
    assert len(result.person_assessments) == 1
    assert result.person_assessments[0].person_id == 1
    assert result.person_assessments[0].person_risk_score == 0.8
    assert len(result.evidence_rows) == 1
    assert result.evidence_rows[0].source_kind == "news"
    assert result.evidence_rows[0].severity == 0.9
    assert db_session.query(NsaCompanyAssessment).count() == 1
    assert db_session.query(NsaPersonAssessment).count() == 1
    assert db_session.query(NsaEvidence).count() == 1


def test_save_assessment_counts_persisted_evidence_rows(db_session) -> None:
    repo = NsaRepository(db_session)

    result = repo.save_assessment(
        firm_id=1,
        correlation_id="cid-2",
        company_risk_score=0.2,
        people=[
            {
                "person_id": 1,
                "person_risk_score": 0.1,
                "analysis": "low risk",
                "evidence": [
                    {
                        "source_kind": "news",
                        "source_url": "https://example.com/a",
                        "title": "A",
                        "excerpt": "A",
                        "severity": 0.2,
                    },
                    {
                        "source_kind": "registry",
                        "source_url": "https://example.com/b",
                        "title": "B",
                        "excerpt": "B",
                        "severity": 0.3,
                    },
                ],
            }
        ],
    )

    assert len(result.evidence_rows) == 2
    assert db_session.query(NsaEvidence).count() == 2
