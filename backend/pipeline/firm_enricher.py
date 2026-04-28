"""Post-ingestion firm enrichment.

After all articles for a pipeline run have been processed, this service
fills in missing business-critical fields on each firm — particularly
``founded_at`` which is required for timeline bucketing.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tarkov.database.models import Event, Firm

logger = logging.getLogger(__name__)


class FirmEnricher:
    """Enriches firm records with data inferred from their events."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def enrich(self, firm_id: int) -> None:
        firm = self._db.get(Firm, firm_id)
        if firm is None:
            logger.warning("FirmEnricher: firm %d not found", firm_id)
            return

        changed = False

        if firm.founded_at is None:
            founded = self._infer_founded_at(firm_id)
            if founded is not None:
                firm.founded_at = founded
                changed = True
                logger.info("firm %d: inferred founded_at=%s", firm_id, founded.isoformat())

        if not firm.country or firm.country == "PL":
            country = self._infer_country(firm_id)
            if country:
                firm.country = country
                changed = True

        if changed:
            self._db.flush()

    def enrich_all(self, firm_ids: list[int]) -> None:
        for fid in firm_ids:
            try:
                self.enrich(fid)
            except Exception:
                logger.exception("FirmEnricher failed for firm %d", fid)

    def _infer_founded_at(self, firm_id: int) -> datetime | None:
        """Use the earliest event date as a proxy for the founding date.

        This is a heuristic: the earliest known event mentioning the firm
        predates or approximates when the firm became publicly relevant.
        A future LLM-based or registry-API lookup can replace this.
        """
        row = self._db.execute(
            select(Event.occurred_at)
            .where(Event.firm_id == firm_id)
            .order_by(Event.occurred_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        return row

    def _infer_country(self, firm_id: int) -> str | None:
        """Infer country from registration numbers on the firm row."""
        firm = self._db.get(Firm, firm_id)
        if firm is None:
            return None
        if firm.nip or firm.regon or firm.krs:
            return "PL"
        return None
