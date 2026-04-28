from __future__ import annotations

import json
import logging

from eem._types import _EventFields, _EventRow
from eem.llm._client import chat_completion
from eem.llm._prompts import SYSTEM_PROMPT, build_user_message
from reasoning.collectors.eem_collector import EEMTraceCollector
from reasoning.schemas import EEMReasoningTrace

logger = logging.getLogger(__name__)

_VALID_TIERS = {"tier-1", "tier-2", "tier-3"}


class _ParseError(Exception):
    pass


def _analyze_event(event: _EventRow, firm_name: str) -> tuple[_EventFields, EEMReasoningTrace]:
    user_msg = build_user_message(event, firm_name)
    collector = EEMTraceCollector(event.event_id, firm_name)
    
    try:
        raw = chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
        )
        fields = _parse_response(raw)
        collector.record_llm_success(fields, raw)
    except Exception as exc:
        logger.warning("Falling back to deterministic EEM analysis for event %s: %s", event.event_id, exc)
        fields = _fallback_fields(event, firm_name)
        collector.record_fallback(exc)
        collector.record_deterministic_result(fields, event_type=event.event_type)
    
    trace = collector.collect()
    return fields, trace


def _fallback_fields(event: _EventRow, firm_name: str) -> _EventFields:
    lowered = f"{event.title} {event.source_text_quote or ''}".lower()
    if event.event_type in {"investment", "expansion", "partnership"}:
        sentiment = 0.35
        impact = min(10.0, max(1.0, event.risk_level * 0.6))
        source_tier = "tier-2"
        keywords = ["inwestycja", "wzrost", "partnerstwo"]
    else:
        sentiment = -0.65
        impact = -min(10.0, max(1.0, float(event.risk_level)))
        source_tier = "tier-1" if any(term in lowered for term in ("prokuratura", "knf", "cba", "sąd")) else "tier-2"
        keywords = _fallback_keywords(event.event_type)

    excerpt = (
        f"{firm_name}: {event.title}. "
        f"{event.source_text_quote or 'Opis sugeruje zdarzenie wymagające dalszej analizy.'}"
    )[:260]
    entities = [firm_name, *[person.name for person in event.people]]
    deduped_entities = list(dict.fromkeys(entity for entity in entities if entity))
    return _EventFields(
        sentiment=sentiment,
        impact=impact,
        source_tier=source_tier,
        keywords=keywords,
        excerpt=excerpt,
        entities=deduped_entities,
    )


def _fallback_keywords(event_type: str) -> list[str]:
    mapping = {
        "money_laundering": ["pranie pieniędzy", "AML", "transakcje podejrzane"],
        "fraud": ["oszustwo", "nadużycie", "wyłudzenie"],
        "regulatory_action": ["postępowanie", "nadzór", "kara"],
        "sanctions": ["sankcje", "monitoring", "ryzyko reputacyjne"],
        "bankruptcy": ["upadłość", "restrukturyzacja", "niewypłacalność"],
        "corruption": ["korupcja", "łapownictwo", "śledztwo"],
    }
    return mapping.get(event_type, ["analiza", "ryzyko", "zdarzenie"])


def _parse_response(raw: str) -> _EventFields:
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise _ParseError(f"Invalid JSON from LLM: {exc}") from exc

    try:
        sentiment = float(data["sentiment"])
        impact = float(data["impact"])
        source_tier = str(data["source_tier"])
        keywords = list(data["keywords"])
        excerpt = str(data["excerpt"])
        entities = list(data["entities"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _ParseError(f"Missing or wrong-typed field: {exc}") from exc

    if not -1.0 <= sentiment <= 1.0:
        raise _ParseError(f"sentiment={sentiment} outside [-1, 1]")
    if not -10.0 <= impact <= 10.0:
        raise _ParseError(f"impact={impact} outside [-10, 10]")
    if source_tier not in _VALID_TIERS:
        raise _ParseError(f"source_tier='{source_tier}' not in {_VALID_TIERS}")
    if not excerpt:
        raise _ParseError("excerpt is empty")
    if not all(isinstance(k, str) for k in keywords):
        raise _ParseError("keywords must be a list of strings")
    if not all(isinstance(e, str) for e in entities):
        raise _ParseError("entities must be a list of strings")

    return _EventFields(
        sentiment=sentiment,
        impact=impact,
        source_tier=source_tier,
        keywords=[str(k) for k in keywords],
        excerpt=excerpt,
        entities=[str(e) for e in entities],
    )
