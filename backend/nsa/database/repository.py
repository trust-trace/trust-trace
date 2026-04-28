from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from nsa.database.models import NsaCompanyAssessment, NsaEvidence, NsaPersonAssessment
from tarkov.database.models import Event, Firm, Person, Source


@dataclass(frozen=True)
class CompanyContext:
    firm: Firm
    people: list[Person]
    events: list[Event]
    sources: list[Source]


@dataclass(frozen=True)
class AssessmentResult:
    company_assessment: NsaCompanyAssessment
    person_assessments: list[NsaPersonAssessment]
    evidence_rows: list[NsaEvidence]


class NsaRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load_company_context(self, firm_id: int) -> CompanyContext:
        firm = self.session.get(Firm, firm_id)
        if firm is None:
            raise LookupError(f"Firm {firm_id} not found")
        people = list(self.session.scalars(select(Person).where(Person.firm_id == firm_id)).all())
        events = list(self.session.scalars(select(Event).where(Event.firm_id == firm_id).options(selectinload(Event.sources))).all())
        sources = [source for event in events for source in event.sources]
        return CompanyContext(firm=firm, people=people, events=events, sources=sources)

    def save_assessment(self, *, firm_id: int, correlation_id: str, company_risk_score: float, people: list[dict]) -> AssessmentResult:
        try:
            company = NsaCompanyAssessment(
                firm_id=firm_id,
                correlation_id=correlation_id,
                company_risk_score=company_risk_score,
                people_scored=len(people),
            )
            self.session.add(company)
            self.session.flush()
            people_rows: list[NsaPersonAssessment] = []
            evidence_rows: list[NsaEvidence] = []
            for row in people:
                person = NsaPersonAssessment(
                    company_assessment_id=company.id,
                    person_id=row["person_id"],
                    person_risk_score=row["person_risk_score"],
                    analysis=row["analysis"],
                )
                self.session.add(person)
                self.session.flush()
                people_rows.append(person)
                for item in row.get("evidence", []):
                    ev = NsaEvidence(
                        person_assessment_id=person.id,
                        source_kind=item["source_kind"],
                        source_url=item["source_url"],
                        title=item.get("title"),
                        excerpt=item.get("excerpt"),
                        severity=item["severity"],
                    )
                    self.session.add(ev)
                    self.session.flush()
                    evidence_rows.append(ev)
            self.session.commit()
            return AssessmentResult(company_assessment=company, person_assessments=people_rows, evidence_rows=evidence_rows)
        except Exception:
            self.session.rollback()
            raise
