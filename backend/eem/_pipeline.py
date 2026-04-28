from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import os

import eem.config as config
from eem._types import FirmNotFoundError, _EventFields, _EventRow
from eem.database._repos import _EnrichmentRepo, _EventReader, _FirmScoreRepo, _FirmScoreTimelineRepo
from eem.database.session import get_db, init_engine
from eem.llm._analyzer import _ParseError, _analyze_event
from timeline.buckets import TimelineBucket, compute_timeline_buckets
from reasoning.storage import ReasoningTraceRepository

logger = logging.getLogger(__name__)


@dataclass
class EEMTimelineEntry:
    bucket_index: int
    bucket_start: datetime
    bucket_end: datetime
    score: int              # 0–100
    risk: str               # high/medium/low
    event_count: int
    keywords: list[str]


def _compute_score(
    impacts: list[float],
    all_keywords: list[list[str]],
) -> tuple[int, str, list[str]]:
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

    flat_keywords = [kw for kws in all_keywords for kw in kws]
    top_keywords = [kw for kw, _ in Counter(flat_keywords).most_common(6)]

    return score, risk, top_keywords


def _run(firm_id: int) -> list[EEMTimelineEntry]:
    """Enrich classical events and produce an 8-bucket timeline score."""
    database_url = os.environ.get("DATABASE_URL") or config.DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in environment")

    init_engine(database_url)

    with get_db() as db:
        reader = _EventReader(db)
        enrichment_repo = _EnrichmentRepo(db)
        score_repo = _FirmScoreRepo(db)
        timeline_repo = _FirmScoreTimelineRepo(db)
        trace_repo = ReasoningTraceRepository(db)

        firm_name, firm_founded_at, firm_created_at = reader.get_firm_info(firm_id)
        events = reader.load_classical_events(firm_id)

        # Determine founding date for timeline bucketing
        founding = firm_founded_at or firm_created_at or datetime.utcnow()
        buckets = compute_timeline_buckets(founding)

        # Phase 1: LLM enrichment per event (unchanged — not bucket-dependent)
        impact_map: dict[str, tuple[float, list[str]]] = {}
        for event in events:
            try:
                fields, trace = _analyze_event(event, firm_name)
                enrichment_repo.upsert(event.event_id, fields, config.EEM_MODEL)
                trace_repo.save(
                    classifier_name="EEM",
                    entity_type="event",
                    entity_id=event.event_id,
                    trace_data=trace.model_dump(),
                    correlation_id=None,
                )
                fields.reasoning_trace = trace
                impact_map[event.event_id] = (fields.impact, fields.keywords)
            except _ParseError as exc:
                logger.warning("Skipping event %s — parse error: %s", event.event_id, exc)
            except Exception as exc:
                logger.warning("Skipping event %s — unexpected error: %s", event.event_id, exc)

        # Phase 2: Cumulative scoring per bucket
        run_id = str(uuid.uuid4())
        timeline: list[EEMTimelineEntry] = []

        for bucket in buckets:
            cumulative_events = [e for e in events if e.occurred_at < bucket.end]
            bucket_impacts = [
                impact_map[e.event_id][0]
                for e in cumulative_events
                if e.event_id in impact_map
            ]
            bucket_keywords = [
                impact_map[e.event_id][1]
                for e in cumulative_events
                if e.event_id in impact_map
            ]

            score, risk, top_keywords = _compute_score(bucket_impacts, bucket_keywords)

            # Events actually within this bucket (for event_count display)
            if bucket.index == 0:
                events_in_bucket = [
                    e for e in events
                    if e.occurred_at < bucket.end
                ]
            else:
                prev_end = buckets[bucket.index - 1].end
                events_in_bucket = [
                    e for e in events
                    if prev_end <= e.occurred_at < bucket.end
                ]

            entry = EEMTimelineEntry(
                bucket_index=bucket.index,
                bucket_start=bucket.start,
                bucket_end=bucket.end,
                score=score,
                risk=risk,
                event_count=len(events_in_bucket),
                keywords=top_keywords,
            )
            timeline.append(entry)

        # Persist timeline rows
        timeline_repo.upsert_timeline(firm_id, run_id, timeline)

        # Also update the legacy single-score table with the latest bucket's values
        latest = timeline[-1]
        all_impacts = [impact_map[e.event_id][0] for e in events if e.event_id in impact_map]
        all_keywords_lists = [impact_map[e.event_id][1] for e in events if e.event_id in impact_map]
        _, _, top_kw = _compute_score(all_impacts, all_keywords_lists)
        previous_history = score_repo.get_history(firm_id)
        trend = (latest.score - previous_history[-1]) if previous_history else 0
        updated_history = (previous_history + [latest.score])[-12:]
        score_repo.upsert(firm_id, latest.score, latest.risk, trend, updated_history, top_kw)

        db.commit()

    logger.info(
        "firm_id=%d enriched %d/%d events → timeline of %d buckets, latest score=%d risk=%s",
        firm_id, len(impact_map), len(events), len(timeline),
        timeline[-1].score, timeline[-1].risk,
    )
    return timeline
