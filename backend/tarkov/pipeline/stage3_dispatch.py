"""Helpers for wiring Tarkov's post-processing dispatch."""

from __future__ import annotations

from tarkov.config import Config
from tarkov.pipeline.event_handlers import AMLScoringEventHandler
from tarkov.pipeline.result_emitter import ResultEmitter
from tarkov.pipeline.stage3_clients import EventClassifierClient, NSAClient


def build_stage3_result_emitter(
    config: Config,
    *,
    event_classifier_client: EventClassifierClient | None = None,
    nsa_client: NSAClient | None = None,
) -> ResultEmitter:
    emitter = ResultEmitter()
    if not config.enable_stage3_dispatch:
        return emitter

    handler = AMLScoringEventHandler(
        event_classifier_client=event_classifier_client or EventClassifierClient(config.event_classifier_url),
        nsa_client=nsa_client or NSAClient(config.nsa_url),
    )
    emitter.register_async_handler(handler.handle_parsed_event)
    return emitter
