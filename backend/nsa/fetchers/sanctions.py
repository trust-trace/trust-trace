from __future__ import annotations

import os

import requests

from nsa.fetchers.base import BasePersonFetcher, CompanyContextLike, FetchOutcome, PersonLike
from nsa.schemas.domain import PersonEvidence


class SanctionsFetcher(BasePersonFetcher):
    source_kind = "sanctions"

    def __init__(self, endpoint_url: str | None = None) -> None:
        self.endpoint_url = endpoint_url or os.getenv("NSA_SANCTIONS_SEARCH_URL")

    def _search(self, name: str) -> list[dict]:
        if not self.endpoint_url:
            return []
        try:
            response = requests.get(self.endpoint_url, params={"q": name}, timeout=2)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError):
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("results")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []

    def fetch(self, person: PersonLike, company_context: CompanyContextLike) -> FetchOutcome:
        name = getattr(company_context, "name", "") or getattr(person, "name", "")
        rows = self._search(name)
        evidence = tuple(item for row in rows if (item := self._map_row(row)) is not None)
        return FetchOutcome(person_id=person.id, evidence=evidence)

    def _map_row(self, row: dict) -> PersonEvidence | None:
        try:
            return PersonEvidence(
                source_kind=self.source_kind,
                source_url=row["url"],
                title=row.get("title"),
                excerpt=row.get("excerpt"),
                severity=1.0,
                confidence=0.98,
                claim_type="sanctions_hit",
            )
        except (KeyError, TypeError, ValueError):
            return None
