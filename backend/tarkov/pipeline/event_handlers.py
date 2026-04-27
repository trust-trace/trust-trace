"""Stage 3 routing handlers.

Tarkov dispatches to event_classifier and nsa only.
Connection/network scoring (TrustWeb) is handled by a separate downstream module.
"""

from __future__ import annotations

import asyncio

from tarkov.schemas.parsed_result import ParsingEvent
from tarkov.utils.logger import get_logger


logger = get_logger(__name__)


class AMLScoringEventHandler:
    def __init__(self, event_classifier_client, nsa_client):
        self.event_classifier = event_classifier_client
        self.nsa = nsa_client

    async def handle_parsed_event(self, event: ParsingEvent):
        parsed = event.parsed_result
        cid = event.correlation_id

        tasks = []
        if "event_classifier" in event.target_modules and parsed.events:
            tasks.append(self.event_classifier.score_events(parsed.company_matches, parsed.events, cid))
        if "nsa" in event.target_modules and parsed.people:
            tasks.append(self.nsa.score_people(parsed.company_matches, parsed.people, cid))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception("stage3 scoring task failed idx=%s correlation_id=%s: %s", idx, cid, result)
        logger.info("stage3 scoring completed correlation_id=%s", cid)
        return results
