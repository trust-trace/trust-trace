"""Firm repository implementation."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tarkov.database.models import Firm, FirmAlias


class FirmRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_firm(self, name: str, ticker: str | None = None, country: str = "PL") -> Firm:
        stmt = select(Firm).where(func.lower(Firm.full_name) == name.lower())
        firm = self.db.execute(stmt).scalar_one_or_none()
        if firm is None and ticker:
            stmt = select(Firm).join(FirmAlias).where(func.lower(FirmAlias.alias) == ticker.lower())
            firm = self.db.execute(stmt).scalar_one_or_none()

        if firm is not None:
            return firm

        firm = Firm(full_name=name, country=country)
        self.db.add(firm)
        self.db.flush()
        self.add_alias(firm.id, name, "name", is_primary=True)
        if ticker:
            self.add_alias(firm.id, ticker, "ticker")
        self.db.flush()
        return firm

    def add_alias(
        self,
        firm_id: int,
        alias: str,
        alias_type: str,
        confidence: float | None = None,
        is_primary: bool = False,
    ) -> FirmAlias:
        existing = self.db.execute(
            select(FirmAlias).where(
                FirmAlias.firm_id == firm_id,
                func.lower(FirmAlias.alias) == alias.lower(),
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        firm_alias = FirmAlias(
            firm_id=firm_id,
            alias=alias,
            alias_type=alias_type,
            confidence=confidence,
            is_primary=is_primary,
        )
        self.db.add(firm_alias)
        self.db.flush()
        return firm_alias

    def find_by_alias(self, alias: str) -> Optional[Firm]:
        stmt = (
            select(Firm)
            .join(FirmAlias)
            .where(or_(func.lower(FirmAlias.alias) == alias.lower(), func.lower(Firm.full_name) == alias.lower()))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_firms(self) -> list[Firm]:
        return list(self.db.execute(select(Firm).order_by(Firm.id)).scalars().all())
