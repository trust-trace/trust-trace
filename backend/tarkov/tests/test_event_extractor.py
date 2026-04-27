from __future__ import annotations

from tarkov.extraction.event_extractor import EventExtractor
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


def test_money_laundering_detection():
    extractor = EventExtractor()
    events = extractor.extract_events_keyword_based(SAMPLE_ARTICLE_1)
    event_types = {event.event_type for event in events}
    assert "money_laundering" in event_types or "fraud" in event_types


def test_risk_level_calculation():
    extractor = EventExtractor()
    risk = extractor.calculate_risk_level("fraud", ["fraud", "ponzi"])
    assert risk >= 8
