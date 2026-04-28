from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nsa.schemas.api import ScoreCompanyResponse
from nsa.schemas.domain import PersonEvidence, PersonScoreInput
from nsa.scoring.rules import score_person
from reasoning.storage import ReasoningTraceRepository


@dataclass(frozen=True)
class NSAService:
    repository: Any
    fetchers: tuple[Any, ...]

    def __init__(self, repository: Any, fetchers: list[Any] | tuple[Any, ...]) -> None:
        object.__setattr__(self, "repository", repository)
        object.__setattr__(self, "fetchers", tuple(fetchers))

    def score_company(self, firm_id: int, correlation_id: str, db_session: Any = None) -> ScoreCompanyResponse:
        company_context: Any = self.repository.load_company_context(firm_id)
        people_payload: list[dict] = []
        person_scores: list[float] = []
        evidence_count = 0
        trace_repo = ReasoningTraceRepository(db_session) if db_session else None

        for person in company_context.people:
            evidence: list[PersonEvidence] = []
            for fetcher in self.fetchers:
                try:
                    outcome = fetcher.fetch(person=person, company_context=company_context)
                except Exception:
                    continue
                if outcome.person_id != person.id:
                    raise ValueError(
                        f"Fetcher {fetcher.__class__.__name__} returned evidence for person {outcome.person_id} "
                        f"while processing person {person.id}"
                    )
                evidence.extend(outcome.evidence)
            evidence_count += len(evidence)

            person_input = PersonScoreInput(
                person_id=person.id,
                person_name=getattr(person, "name", ""),
                role=getattr(person, "role", None),
                evidence=tuple(evidence),
            )
            result, trace = score_person(person_input)
            
            # Store trace if database session is provided
            if trace_repo:
                trace_repo.save(
                    classifier_name="NSA",
                    entity_type="person",
                    entity_id=str(person.id),
                    trace_data=trace.model_dump(),
                    correlation_id=correlation_id,
                )
            
            person_scores.append(result.person_risk_score)
            people_payload.append(
                {
                    "person_id": person.id,
                    "person_risk_score": result.person_risk_score,
                    "analysis": result.analysis,
                    "evidence": [
                        {
                            "source_kind": item.source_kind,
                            "source_url": str(item.source_url),
                            "title": item.title,
                            "excerpt": item.excerpt,
                            "severity": item.severity,
                        }
                        for item in evidence
                    ],
                }
            )

        company_risk_score = sum(person_scores) / len(person_scores) if person_scores else 0.0
        self.repository.save_assessment(
            firm_id=firm_id,
            correlation_id=correlation_id,
            company_risk_score=company_risk_score,
            people=people_payload,
        )
        return ScoreCompanyResponse(
            status="ok",
            firm_id=firm_id,
            company_risk_score=company_risk_score,
            people_scored=len(people_payload),
            evidence_count=evidence_count,
        )
