"""Firm repository (dual-mode):

This repository still accepts a SQLAlchemy session for Postgres operations but also
provides helper methods to create/update Company nodes in Neo4j graph.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tarkov.database.models import Firm, FirmAlias
from tarkov.database.session import get_neo4j_session


class FirmRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Postgres-backed methods (existing) ---
    def get_or_create_firm(self, name: str, ticker: str | None = None, country: str = "PL") -> Firm:
        existing = self.find_by_alias(name)
        if existing is not None:
            return existing

        if ticker:
            existing = self.find_by_alias(ticker)
            if existing is not None:
                return existing

        firm = Firm(full_name=name, country=country)
        self.db.add(firm)
        self.db.flush()

        self.add_alias(firm.id, name, "name", confidence=1.0, is_primary=True)
        if ticker:
            self.add_alias(firm.id, ticker, "ticker", confidence=1.0)

        # ensure graph node exists
        try:
            with get_neo4j_session() as g:
                g.create_node("Company", {"company_id": firm.id, "full_name": firm.full_name, "country": firm.country})
        except Exception:
            # Neo4j optional — ignore errors here
            pass

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
        if existing:
            return existing

        obj = FirmAlias(
            firm_id=firm_id,
            alias=alias,
            alias_type=alias_type,
            confidence=confidence,
            is_primary=is_primary,
        )
        self.db.add(obj)
        self.db.flush()

        # Also add alias property in Neo4j if company node exists
        try:
            with get_neo4j_session() as g:
                q = "MATCH (c:Company {company_id: $company_id}) CREATE (a:Alias {alias: $alias, alias_type: $alias_type, confidence: $confidence, is_primary: $is_primary})-[:ALIAS_OF]->(c)"
                g.run(q, company_id=firm_id, alias=alias, alias_type=alias_type, confidence=confidence, is_primary=is_primary)
        except Exception:
            pass

        return obj

    def find_by_alias(self, alias: str) -> Optional[Firm]:
        stmt = (
            select(Firm)
            .outerjoin(FirmAlias, FirmAlias.firm_id == Firm.id)
            .where(
                or_(
                    func.lower(Firm.full_name) == alias.lower(),
                    func.lower(FirmAlias.alias) == alias.lower(),
                )
            )
        )
        return self.db.execute(stmt).scalars().first()

    def list_firms(self) -> list[Firm]:
        return list(self.db.execute(select(Firm).order_by(Firm.id)).scalars().all())
