"""Handlers that route parsed events to AML scoring modules."""

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
        parsed_result = event.parsed_result
        correlation_id = event.correlation_id

        tasks = []
        if "event_classifier" in event.target_modules and parsed_result.events:
            tasks.append(
                self.event_classifier.score_events(
                    parsed_result.company_matches,
                    parsed_result.events,
                    correlation_id,
                )
            )

        if "nsa" in event.target_modules and parsed_result.people:
            tasks.append(
                self.nsa.score_people(
                    parsed_result.company_matches,
                    parsed_result.people,
                    correlation_id,
                )
            )

        if "trustweb" in event.target_modules and parsed_result.connections:
            tasks.append(
                self.trustweb.score_network(
                    parsed_result.company_matches,
                    parsed_result.connections,
                    correlation_id,
                )
            )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Scoring completed for correlation_id=%s", correlation_id)
        return results
