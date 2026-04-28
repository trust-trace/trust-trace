from __future__ import annotations

import logging
from collections import Counter
import os

import eem.config as config
from eem._types import FirmNotFoundError, _EventFields
from eem.database._repos import _EnrichmentRepo, _EventReader, _FirmScoreRepo
from eem.database.session import get_db, init_engine
from eem.llm._analyzer import _ParseError, _analyze_event

logger = logging.getLogger(__name__)


def _compute_score(
    impacts: list[float],
    previous_history: list[int],
    all_keywords: list[list[str]],
) -> tuple[int, str, int, list[int], list[str]]:
    if not impacts:
        score = 50
    else:
        per_event = [max(0, min(100, round(50 + imp * 5))) for imp in impacts]
        score = round(sum(per_event) / len(per_event))

    if score <= 40:
        risk = "high"
    elif score <= 65:
        risk = "medium"
    else:
        risk = "low"

    trend = (score - previous_history[-1]) if previous_history else 0
    updated_history = (previous_history + [score])[-12:]

    flat_keywords = [kw for kws in all_keywords for kw in kws]
    top_keywords = [kw for kw, _ in Counter(flat_keywords).most_common(6)]

    return score, risk, trend, updated_history, top_keywords


def _run(firm_id: int) -> float:
    database_url = os.environ.get("DATABASE_URL") or config.DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in environment")

    init_engine(database_url)

    with get_db() as db:
        reader = _EventReader(db)
        enrichment_repo = _EnrichmentRepo(db)
        score_repo = _FirmScoreRepo(db)

        firm_name = reader.get_firm_name(firm_id)
        events = reader.load_classical_events(firm_id)

        impacts: list[float] = []
        all_keywords: list[list[str]] = []

        for event in events:
            try:
                fields: _EventFields = _analyze_event(event, firm_name)
                enrichment_repo.upsert(event.event_id, fields, config.EEM_MODEL)
                impacts.append(fields.impact)
                all_keywords.append(fields.keywords)
            except _ParseError as exc:
                logger.warning("Skipping event %s — parse error: %s", event.event_id, exc)
            except Exception as exc:
                logger.warning("Skipping event %s — unexpected error: %s", event.event_id, exc)

        previous_history = score_repo.get_history(firm_id)
        score, risk, trend, history, top_keywords = _compute_score(
            impacts, previous_history, all_keywords
        )
        score_repo.upsert(firm_id, score, risk, trend, history, top_keywords)

        db.commit()

    logger.info(
        "firm_id=%d enriched %d/%d events → score=%d risk=%s trend=%+d",
        firm_id,
        len(impacts),
        len(events),
        score,
        risk,
        trend,
    )
    return float(score)
