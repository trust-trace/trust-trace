from __future__ import annotations

from unittest.mock import MagicMock

from market.lookup.ticker_search import TickerSearch
from market.schemas.ohlcv import ListingMatch


def _make_listing(symbol: str, exchange: str) -> ListingMatch:
    return ListingMatch(tv_symbol=symbol, tv_exchange=exchange, short_name="Test", currency="PLN")


def test_deduplication_by_exchange():
    adapter = MagicMock()
    adapter.search.return_value = [
        _make_listing("PKNORLEN", "GPW"),
        _make_listing("PKNORLEN2", "GPW"),  # duplicate exchange
        _make_listing("PKN", "XETRA"),
    ]

    searcher = TickerSearch(adapter)
    results = searcher.find_listings("PKN Orlen")

    assert len(results) == 2
    exchanges = {r.tv_exchange for r in results}
    assert exchanges == {"GPW", "XETRA"}


def test_empty_when_no_results():
    adapter = MagicMock()
    adapter.search.return_value = []

    searcher = TickerSearch(adapter)
    results = searcher.find_listings("Unknown Corp")
    assert results == []
