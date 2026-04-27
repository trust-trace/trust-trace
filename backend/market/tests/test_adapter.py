from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from market.adapters.tradingview_adapter import TradingViewAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "sample_search_result.json"


def _raw_results() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def test_search_filters_stock_type():
    adapter = TradingViewAdapter.__new__(TradingViewAdapter)
    adapter._tv = MagicMock()
    adapter._tv.search_symbol.return_value = _raw_results()

    listings = adapter.search("PKN Orlen")

    # fixture has 2 stock entries and 1 fund — only stocks should pass
    assert len(listings) == 2
    symbols = {l.tv_symbol for l in listings}
    assert "PKNORLEN" in symbols


def test_search_returns_empty_on_exception():
    adapter = TradingViewAdapter.__new__(TradingViewAdapter)
    adapter._tv = MagicMock()
    adapter._tv.search_symbol.side_effect = Exception("network error")

    listings = adapter.search("Anything")
    assert listings == []


def test_fetch_returns_empty_on_none_df():
    adapter = TradingViewAdapter.__new__(TradingViewAdapter)
    adapter._tv = MagicMock()
    adapter._tv.get_hist.return_value = None

    records = adapter.fetch("PKNORLEN", "GPW", 10)
    assert records == []
