from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from market.pipeline.fetcher import MarketFetcher
from market.schemas.ohlcv import ListingMatch, OHLCVRecord


def _make_listing(symbol: str = "PKNORLEN", exchange: str = "GPW") -> ListingMatch:
    return ListingMatch(tv_symbol=symbol, tv_exchange=exchange, short_name="PKN ORLEN SA", currency="PLN")


def _make_records(n: int = 3) -> list[OHLCVRecord]:
    return [
        OHLCVRecord(date=date(2024, 1, i + 1), open=100.0, high=105.0, low=98.0, close=102.0, volume=1000)
        for i in range(n)
    ]


def _make_fetcher(adapter_search, adapter_fetch) -> tuple[MarketFetcher, MagicMock]:
    adapter = MagicMock()
    adapter.search.side_effect = adapter_search
    adapter.fetch.side_effect = adapter_fetch

    db = MagicMock()
    repo = MagicMock()
    repo.upsert_firm_market.return_value = MagicMock()
    repo.upsert_market_data_batch.return_value = 3

    fetcher = MarketFetcher.__new__(MarketFetcher)
    fetcher._adapter = adapter
    fetcher._db = db
    fetcher._repo = repo
    from market.lookup.ticker_search import TickerSearch
    fetcher._search = TickerSearch(adapter)

    return fetcher, db


def test_fetch_company_not_found():
    fetcher, db = _make_fetcher(
        adapter_search=lambda name: [],
        adapter_fetch=lambda s, e, n_bars: [],
    )
    result = fetcher.fetch_company(1, "Unknown Corp", 30)
    assert result.found is False
    assert result.charts == []
    db.commit.assert_not_called()


def test_fetch_company_found():
    listing = _make_listing()
    records = _make_records(3)

    fetcher, db = _make_fetcher(
        adapter_search=lambda name: [listing],
        adapter_fetch=lambda s, e, n_bars: records,
    )

    result = fetcher.fetch_company(42, "PKN Orlen", 30)

    assert result.found is True
    assert len(result.charts) == 1
    assert result.charts[0].listing == listing
    assert len(result.charts[0].records) == 3
    db.commit.assert_called_once()
