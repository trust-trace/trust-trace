"""HTTP clients used to dispatch parsed results to Stage 3 modules."""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class BaseScoringClient:
    base_url: str
    route: str
    timeout_seconds: int = 15

    def _post(self, payload: dict) -> dict:
        if not self.base_url:
            return {"status": "skipped", "reason": "missing_base_url"}
        url = f"{self.base_url.rstrip('/')}{self.route}"
        response = requests.post(url, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "http_status": response.status_code}


class EventClassifierClient(BaseScoringClient):
    def __init__(self, base_url: str):
        super().__init__(base_url=base_url, route="/score/events")

    async def score_events(self, company_matches, events, correlation_id):
        payload = {
            "correlation_id": correlation_id,
            "company_matches": company_matches,
            "events": [event.model_dump(mode="json") for event in events],
        }
        from asyncio import to_thread

        return await to_thread(self._post, payload)


class NSAClient(BaseScoringClient):
    def __init__(self, base_url: str):
        super().__init__(base_url=base_url, route="/score/people")

    async def score_people(self, company_matches, people, correlation_id):
        payload = {
            "correlation_id": correlation_id,
            "company_matches": company_matches,
            "people": [person.model_dump(mode="json") for person in people],
        }
        from asyncio import to_thread

        return await to_thread(self._post, payload)


class TrustWebClient(BaseScoringClient):
    def __init__(self, base_url: str):
        super().__init__(base_url=base_url, route="/score/network")

    async def score_network(self, company_matches, connections, correlation_id):
        payload = {
            "correlation_id": correlation_id,
            "company_matches": company_matches,
            "connections": [conn.model_dump(mode="json") for conn in connections],
        }
        from asyncio import to_thread

        return await to_thread(self._post, payload)
