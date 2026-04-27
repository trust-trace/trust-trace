"""Stage 3 routing handlers."""

from __future__ import annotations

import asyncio

from tarkov.schemas.parsed_result import ParsingEvent
from tarkov.utils.logger import get_logger


logger = get_logger(__name__)


class AMLScoringEventHandler:
    def __init__(self, event_classifier_client, nsa_client, trustweb_client):
        self.event_classifier = event_classifier_client
        self.nsa = nsa_client
        self.trustweb = trustweb_client

    async def handle_parsed_event(self, event: ParsingEvent):
        parsed = event.parsed_result
        cid = event.correlation_id

        tasks = []
        if "event_classifier" in event.target_modules and parsed.events:
            tasks.append(self.event_classifier.score_events(parsed.company_matches, parsed.events, cid))
        if "nsa" in event.target_modules and parsed.people:
            tasks.append(self.nsa.score_people(parsed.company_matches, parsed.people, cid))
        if "trustweb" in event.target_modules and parsed.connections:
            tasks.append(self.trustweb.score_network(parsed.company_matches, parsed.connections, cid))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception("stage3 scoring task failed idx=%s correlation_id=%s: %s", idx, cid, result)
        logger.info("stage3 scoring completed correlation_id=%s", cid)
        return results
