from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from market.adapters.base import ExchangeAdapter
from market.database.repository import MarketRepository
from market.lookup.ticker_search import TickerSearch
from market.schemas.ohlcv import ChartData, FetchResult

logger = logging.getLogger(__name__)


class MarketFetcher:
    def __init__(self, adapter: ExchangeAdapter, db: Session) -> None:
        self._search = TickerSearch(adapter)
        self._adapter = adapter
        self._repo = MarketRepository(db)
        self._db = db

    def fetch_company(self, firm_id: int, firm_name: str, days: int = 365) -> FetchResult:
        listings = self._search.find_listings(firm_name)

        if not listings:
            logger.info("No listing found for firm_id=%d name=%r", firm_id, firm_name)
            return FetchResult(firm_id=firm_id, firm_name=firm_name, found=False, charts=[])

        charts: list[ChartData] = []
        for listing in listings:
            self._repo.upsert_firm_market(firm_id, listing)

            records = self._adapter.fetch(listing.tv_symbol, listing.tv_exchange, n_bars=days)
            if records:
                count = self._repo.upsert_market_data_batch(firm_id, listing, records)
                logger.info(
                    "firm_id=%d %s:%s — %d bars persisted",
                    firm_id,
                    listing.tv_exchange,
                    listing.tv_symbol,
                    count,
                )
            charts.append(ChartData(listing=listing, records=records))

        self._db.commit()
        return FetchResult(firm_id=firm_id, firm_name=firm_name, found=True, charts=charts)
