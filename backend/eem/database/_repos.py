from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

import eem.config as config
from eem._types import (
    FirmNotFoundError,
    _EventFields,
    _EventRow,
    _PersonRow,
    _SourceRow,
)
from eem.database.models import EventEnrichment, FirmScore

logger = logging.getLogger(__name__)


class _EventReader:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_firm_name(self, firm_id: int) -> str:
        row = self._db.execute(
            text("SELECT full_name FROM firm WHERE id = :fid"),
            {"fid": firm_id},
        ).fetchone()
        if row is None:
            raise FirmNotFoundError(f"No firm with id={firm_id}")
        return row.full_name

    def load_classical_events(self, firm_id: int) -> list[_EventRow]:
        exists = self._db.execute(
            text("SELECT 1 FROM firm WHERE id = :fid"),
            {"fid": firm_id},
        ).fetchone()
        if exists is None:
            raise FirmNotFoundError(f"No firm with id={firm_id}")

        rows = self._db.execute(
            text(
                """
                SELECT unique_id, event_type, title, risk_level,
                       occurred_at, source_text_quote
                FROM event
                WHERE firm_id = :fid AND event_category = 'classical'
                ORDER BY occurred_at ASC
                """
            ),
            {"fid": firm_id},
        ).fetchall()

        return [
            _EventRow(
                event_id=r.unique_id,
                firm_id=firm_id,
                event_type=r.event_type,
                title=r.title,
                risk_level=r.risk_level,
                occurred_at=r.occurred_at,
                source_text_quote=r.source_text_quote,
                sources=self._load_sources(r.unique_id),
                people=self._load_people(r.unique_id),
            )
            for r in rows
        ]

    def get_unprocessed_firm_ids(self) -> list[int]:
        rows = self._db.execute(
            text(
                """
                SELECT DISTINCT e.firm_id
                FROM event e
                LEFT JOIN event_enrichment ee ON ee.event_id = e.unique_id
                WHERE e.event_category = 'classical' AND ee.id IS NULL
                """
            )
        ).fetchall()
        return [r.firm_id for r in rows]

    def _load_sources(self, event_id: str) -> list[_SourceRow]:
        rows = self._db.execute(
            text(
                """
                SELECT title, url, COALESCE(content, '') AS content, published_at
                FROM source
                WHERE event_id = :eid
                """
            ),
            {"eid": event_id},
        ).fetchall()
        limit = config.EEM_SOURCE_EXCERPT_CHARS
        return [
            _SourceRow(
                title=r.title,
                url=r.url,
                published_at=r.published_at,
                content_excerpt=r.content[:limit],
            )
            for r in rows
        ]

    def _load_people(self, event_id: str) -> list[_PersonRow]:
        rows = self._db.execute(
            text(
                """
                SELECT p.name, p.role, pe.role_in_event
                FROM person_event pe
                JOIN person p ON p.id = pe.person_id
                WHERE pe.event_id = :eid
                """
            ),
            {"eid": event_id},
        ).fetchall()
        return [
            _PersonRow(name=r.name, role=r.role, role_in_event=r.role_in_event)
            for r in rows
        ]


class _EnrichmentRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert(self, event_id: str, fields: _EventFields, model: str) -> None:
        existing = self._db.execute(
            select(EventEnrichment).where(EventEnrichment.event_id == event_id)
        ).scalar_one_or_none()

        now = datetime.utcnow()
        kw_json = json.dumps(fields.keywords, ensure_ascii=False)
        ent_json = json.dumps(fields.entities, ensure_ascii=False)

        if existing is None:
            self._db.add(
                EventEnrichment(
                    event_id=event_id,
                    sentiment=fields.sentiment,
                    impact=fields.impact,
                    source_tier=fields.source_tier,
                    keywords=kw_json,
                    excerpt=fields.excerpt,
                    entities=ent_json,
                    model_used=model,
                    enriched_at=now,
                )
            )
        else:
            existing.sentiment = fields.sentiment
            existing.impact = fields.impact
            existing.source_tier = fields.source_tier
            existing.keywords = kw_json
            existing.excerpt = fields.excerpt
            existing.entities = ent_json
            existing.model_used = model
            existing.enriched_at = now

        self._db.flush()


class _FirmScoreRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_history(self, firm_id: int) -> list[int]:
        row = self._db.execute(
            select(FirmScore).where(FirmScore.firm_id == firm_id)
        ).scalar_one_or_none()
        if row is None:
            return []
        return json.loads(row.score_history)

    def upsert(
        self,
        firm_id: int,
        score: int,
        risk: str,
        trend: int,
        history: list[int],
        keywords: list[str],
    ) -> None:
        existing = self._db.execute(
            select(FirmScore).where(FirmScore.firm_id == firm_id)
        ).scalar_one_or_none()

        now = datetime.utcnow()
        history_json = json.dumps(history)
        kw_json = json.dumps(keywords, ensure_ascii=False)

        if existing is None:
            self._db.add(
                FirmScore(
                    firm_id=firm_id,
                    score=score,
                    risk=risk,
                    trend=trend,
                    score_history=history_json,
                    keywords=kw_json,
                    computed_at=now,
                )
            )
        else:
            existing.score = score
            existing.risk = risk
            existing.trend = trend
            existing.score_history = history_json
            existing.keywords = kw_json
            existing.computed_at = now

        self._db.flush()
