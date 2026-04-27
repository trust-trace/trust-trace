from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from market.database.models import FirmMarket, MarketData
from market.schemas.ohlcv import ListingMatch, OHLCVRecord


def _is_sqlite(session: Session) -> bool:
    return "sqlite" in session.bind.dialect.name  # type: ignore[union-attr]


class MarketRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert_firm_market(self, firm_id: int, listing: ListingMatch) -> FirmMarket:
        if _is_sqlite(self._db):
            stmt = (
                sqlite_insert(FirmMarket)
                .values(
                    firm_id=firm_id,
                    symbol=listing.symbol,
                    exchange=listing.exchange,
                    currency=listing.currency,
                    is_active=True,
                    added_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["firm_id", "symbol", "exchange"],
                    set_={"is_active": True},
                )
            )
        else:
            stmt = (
                pg_insert(FirmMarket)
                .values(
                    firm_id=firm_id,
                    symbol=listing.symbol,
                    exchange=listing.exchange,
                    currency=listing.currency,
                    is_active=True,
                    added_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    constraint="uq_firm_listing",
                    set_={"is_active": True},
                )
            )

        self._db.execute(stmt)
        self._db.flush()

        return (
            self._db.query(FirmMarket)
            .filter_by(
                firm_id=firm_id,
                symbol=listing.symbol,
                exchange=listing.exchange,
            )
            .one()
        )

    def upsert_market_data_batch(
        self,
        firm_id: int,
        listing: ListingMatch,
        records: list[OHLCVRecord],
    ) -> int:
        if not records:
            return 0

        now = datetime.utcnow()
        rows = [
            {
                "firm_id": firm_id,
                "symbol": listing.symbol,
                "exchange": listing.exchange,
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "fetched_at": now,
            }
            for r in records
        ]

        if _is_sqlite(self._db):
            stmt = sqlite_insert(MarketData).values(rows).on_conflict_do_update(
                index_elements=["firm_id", "symbol", "exchange", "date"],
                set_={
                    "open": text("excluded.open"),
                    "high": text("excluded.high"),
                    "low": text("excluded.low"),
                    "close": text("excluded.close"),
                    "volume": text("excluded.volume"),
                    "fetched_at": text("excluded.fetched_at"),
                },
            )
        else:
            stmt = pg_insert(MarketData).values(rows).on_conflict_do_update(
                constraint="uq_firm_date",
                set_={
                    "open": text("EXCLUDED.open"),
                    "high": text("EXCLUDED.high"),
                    "low": text("EXCLUDED.low"),
                    "close": text("EXCLUDED.close"),
                    "volume": text("EXCLUDED.volume"),
                    "fetched_at": text("EXCLUDED.fetched_at"),
                },
            )

        self._db.execute(stmt)
        self._db.flush()
        return len(rows)
