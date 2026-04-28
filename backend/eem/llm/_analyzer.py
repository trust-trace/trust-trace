from __future__ import annotations

import json
import logging

from eem._types import _EventFields, _EventRow
from eem.llm._client import chat_completion
from eem.llm._prompts import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

_VALID_TIERS = {"tier-1", "tier-2", "tier-3"}


class _ParseError(Exception):
    pass


def _analyze_event(event: _EventRow, firm_name: str) -> _EventFields:
    user_msg = build_user_message(event, firm_name)
    raw = chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
    )
    return _parse_response(raw)


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
