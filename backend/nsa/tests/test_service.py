from __future__ import annotations

import pytest

from nsa.fetchers.base import FetchOutcome
from nsa.fetchers.news import NewsFetcher
from nsa.fetchers.registry import RegistryFetcher
from nsa.fetchers.sanctions import SanctionsFetcher
from nsa.schemas.domain import PersonEvidence
from nsa.scoring.service import NSAService


class PersonStub:
    def __init__(self, person_id: int) -> None:
        self.id = person_id


class PersonContextStub:
    def __init__(self, person_id: int, name: str, role: str | None = None) -> None:
        self.id = person_id
        self.name = name
        self.role = role


class CompanyContextStub:
    def __init__(self, people: list[PersonContextStub]) -> None:
        self.firm = type("FirmStub", (), {"id": 42})()
        self.people = people
        self.events = []
        self.sources = []


class CompanyContextWithQueryStub:
    def __init__(self, name: str) -> None:
        self.name = name


class RepoStub:
    def __init__(self, people: list[PersonContextStub] | None = None) -> None:
        self.saved = None
        self.people = (
            [
                PersonContextStub(1, "Jane Doe", "director"),
                PersonContextStub(2, "John Doe", None),
            ]
            if people is None
            else people
        )

    def load_company_context(self, firm_id: int) -> CompanyContextStub:
        assert firm_id == 42
        return CompanyContextStub(self.people)

    def save_assessment(self, **kwargs):
        self.saved = kwargs
        return kwargs


class FetcherOne:
    def fetch(self, person, company_context):
        if person.id == 1:
            return FetchOutcome(
                person_id=1,
                evidence=(
                    PersonEvidence(
                        source_kind="news",
                        source_url="https://example.test/1",  # type: ignore[arg-type]
                        title="Article",
                        excerpt="Person 1 mention",
                        severity=0.4,
                        confidence=0.8,
                        claim_type="fraud_allegation",
                    ),
                ),
            )
        return FetchOutcome(person_id=2, evidence=())


class FetcherTwo:
    def fetch(self, person, company_context):
        if person.id == 1:
            return FetchOutcome(
                person_id=1,
                evidence=(
                    PersonEvidence(
                        source_kind="registry",
                        source_url="https://example.test/2",  # type: ignore[arg-type]
                        title="Registry",
                        excerpt="Person 1 registry entry",
                        severity=0.2,
                        confidence=0.9,
                        claim_type="ponzi_link",
                    ),
                ),
            )
        return FetchOutcome(person_id=2, evidence=())


class FailingFetcher:
    def fetch(self, person, company_context):
        raise RuntimeError("boom")


class BadOutcomeFetcher:
    def fetch(self, person, company_context):
        return FetchOutcome(person_id=999, evidence=())


def test_fetchers_return_normalized_person_evidence() -> None:
    outcome = FetchOutcome(
        person_id=10,
        evidence=(
            PersonEvidence(
                source_kind="warning_list",
                source_url="https://example.test/warnings/10",  # type: ignore[arg-type]
                title="Public warning",
                excerpt="John Smith appears in warning list",
                severity=0.9,
                confidence=0.95,
                claim_type="warning_list_hit",
            ),
        ),
    )

    assert outcome.person_id == 10
    assert outcome.evidence[0].claim_type == "warning_list_hit"
    assert outcome.evidence[0].severity == 0.9


def test_sanctions_fetcher_maps_search_rows_to_high_severity_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "url": "https://example.test/sanctions/1",
            "title": "Sanctions entry",
            "excerpt": "John Smith appears on sanctions list",
        }
    ]
    monkeypatch.setattr(SanctionsFetcher, "_search", lambda self, name: rows)

    outcome = SanctionsFetcher().fetch(PersonStub(1), CompanyContextWithQueryStub("John Smith"))

    assert outcome.person_id == 1
    assert len(outcome.evidence) == 1
    evidence = outcome.evidence[0]
    assert evidence.source_kind == "sanctions"
    assert str(evidence.source_url) == "https://example.test/sanctions/1"
    assert evidence.title == "Sanctions entry"
    assert evidence.excerpt == "John Smith appears on sanctions list"
    assert evidence.severity == 1.0
    assert evidence.confidence == 0.98
    assert evidence.claim_type == "sanctions_hit"


def test_registry_fetcher_maps_search_rows_to_registry_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "url": "https://example.test/registry/1",
            "title": "Registry record",
            "excerpt": "Jane Doe listed as director",
        }
    ]
    monkeypatch.setattr(RegistryFetcher, "_search", lambda self, name: rows)

    outcome = RegistryFetcher().fetch(PersonStub(2), CompanyContextWithQueryStub("Jane Doe"))

    assert outcome.person_id == 2
    assert len(outcome.evidence) == 1
    evidence = outcome.evidence[0]
    assert evidence.source_kind == "registry"
    assert str(evidence.source_url) == "https://example.test/registry/1"
    assert evidence.severity == 0.55
    assert evidence.confidence == 0.88
    assert evidence.claim_type in {"fraud_allegation", "ponzi_link", "aml_investigation"}


def test_news_fetcher_maps_search_rows_to_news_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "url": "https://example.test/news/1",
            "title": "Local article",
            "excerpt": "John Doe was mentioned in an investigation article",
        }
    ]
    monkeypatch.setattr(NewsFetcher, "_search", lambda self, name: rows)

    outcome = NewsFetcher().fetch(PersonStub(3), CompanyContextWithQueryStub("John Doe"))

    assert outcome.person_id == 3
    assert len(outcome.evidence) == 1
    evidence = outcome.evidence[0]
    assert evidence.source_kind == "news"
    assert str(evidence.source_url) == "https://example.test/news/1"
    assert evidence.severity == 0.35
    assert evidence.confidence == 0.72
    assert evidence.claim_type == "news_mention"


def test_fetchers_skip_malformed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"title": "Missing URL"}, {"url": "https://example.test/news/2", "title": "Ok"}]
    monkeypatch.setattr(NewsFetcher, "_search", lambda self, name: rows)

    outcome = NewsFetcher().fetch(PersonStub(4), CompanyContextWithQueryStub("Jane Doe"))

    assert outcome.person_id == 4
    assert len(outcome.evidence) == 1
    assert str(outcome.evidence[0].source_url) == "https://example.test/news/2"


@pytest.mark.parametrize(
    ("fetcher_cls", "person_id"),
    [
        (RegistryFetcher, 7),
        (SanctionsFetcher, 8),
        (NewsFetcher, 9),
    ],
)
def test_stub_fetchers_return_empty_outcomes(fetcher_cls: type, person_id: int) -> None:
    fetcher = fetcher_cls()

    outcome = fetcher.fetch(person=PersonStub(person_id), company_context=object())

    assert outcome.person_id == person_id
    assert outcome.evidence == ()


def test_service_loads_fetches_scores_and_persists() -> None:
    repo = RepoStub()
    service = NSAService(repo, [FetcherOne(), FetcherTwo()])

    response = service.score_company(42, "cid-1")

    assert response.status == "ok"
    assert response.firm_id == 42
    assert response.people_scored == 2
    assert response.evidence_count == 2
    assert response.company_risk_score > 0.0
    assert repo.saved is not None
    assert repo.saved["firm_id"] == 42
    assert len(repo.saved["people"]) == 2
    assert len(repo.saved["people"][0]["evidence"]) == 2


def test_service_handles_empty_people_context() -> None:
    repo = RepoStub(people=[])
    service = NSAService(repo, [FetcherOne(), FetcherTwo()])

    response = service.score_company(42, "cid-empty")

    assert response.company_risk_score == 0.0
    assert response.people_scored == 0
    assert response.evidence_count == 0
    assert repo.saved is not None
    assert repo.saved["people"] == []


def test_service_skips_fetcher_failures_and_keeps_scoring() -> None:
    repo = RepoStub()
    service = NSAService(repo, [FailingFetcher(), FetcherOne()])

    response = service.score_company(42, "cid-failover")

    assert response.people_scored == 2
    assert response.evidence_count == 1
    assert repo.saved is not None
    assert len(repo.saved["people"][0]["evidence"]) == 1
