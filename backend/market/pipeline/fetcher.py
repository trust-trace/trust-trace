from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from market.adapters.base import ExchangeAdapter
from market.database.repository import MarketRepository
from market.lookup.ticker_search import TickerSearch
from market.schemas.ohlcv import ChartData, FetchResult
from reasoning.collectors.market_collector import MarketTraceCollector
from reasoning.storage import ReasoningTraceRepository

logger = logging.getLogger(__name__)


class MarketFetcher:
    def __init__(self, adapter: ExchangeAdapter, db: Session) -> None:
        self._search = TickerSearch(adapter)
        self._adapter = adapter
        self._repo = MarketRepository(db)
        self._db = db

    def fetch_company(self, firm_id: int, firm_name: str, days: int = 365) -> tuple[FetchResult, dict]:
        collector = MarketTraceCollector(firm_name, firm_id)
        trace_repo = ReasoningTraceRepository(self._db)
        
        listings = self._search.find_listings(firm_name)
        
        # Record ticker search
        candidates = []
        if hasattr(listings, '__iter__'):
            for listing in listings:
                candidates.append({
                    "name": getattr(listing, "name", ""),
                    "ticker": getattr(listing, "ticker", ""),
                    "exchange": getattr(listing, "exchange", ""),
                    "match_score": getattr(listing, "match_score", 1.0),
                    "selected": True,
                    "reason": "found_in_search",
                })
        collector.record_ticker_search("exact", candidates)

        if not listings:
            logger.info("No listing found for firm_id=%d name=%r", firm_id, firm_name)
            trace = collector.collect()
            return FetchResult(firm_id=firm_id, firm_name=firm_name, found=False, charts=[]), trace.model_dump()

        charts: list[ChartData] = []
        for listing in listings:
            # Record listing selection
            collector.record_listing_selected(
                tv_symbol=listing.tv_symbol,
                tv_exchange=listing.tv_exchange,
                ticker=getattr(listing, "ticker", ""),
                exchange=getattr(listing, "exchange", ""),
            )
            
            self._repo.upsert_firm_market(firm_id, listing)

            records = self._adapter.fetch(listing.tv_symbol, listing.tv_exchange, n_bars=days)
            bars_fetched = len(records) if records else 0
            
            if records:
                count = self._repo.upsert_market_data_batch(firm_id, listing, records)
                logger.info(
                    "firm_id=%d %s:%s — %d bars persisted",
                    firm_id,
                    listing.tv_exchange,
                    listing.tv_symbol,
                    count,
                )
                # Record successful fetch
                collector.record_fetch_result(
                    tv_symbol=listing.tv_symbol,
                    tv_exchange=listing.tv_exchange,
                    bars_fetched=bars_fetched,
                    bars_persisted=count,
                    error=None,
                )
            else:
                # Record failed fetch
                collector.record_fetch_result(
                    tv_symbol=listing.tv_symbol,
                    tv_exchange=listing.tv_exchange,
                    bars_fetched=0,
                    bars_persisted=0,
                    error="No data returned from adapter",
                )
            
            charts.append(ChartData(listing=listing, records=records))

        # Record fetch parameters
        collector.record_fetch_parameters(
            n_bars_requested=days,
            start_date=None,
            end_date=None,
            days_back=days,
        )

        self._db.commit()
        
        result = FetchResult(firm_id=firm_id, firm_name=firm_name, found=True, charts=charts)
        trace = collector.collect()
        
        # Store trace
        trace_repo.save(
            classifier_name="Market",
            entity_type="company",
            entity_id=str(firm_id),
            trace_data=trace.model_dump(),
            correlation_id=None,
        )
        self._db.commit()
        
        return result, trace.model_dump()
