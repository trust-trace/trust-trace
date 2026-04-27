"""Quick smoke test — run from backend/ with: python -m market.smoke_test"""
from __future__ import annotations

import os
import pprint

from dotenv import load_dotenv
load_dotenv()

from market.adapters.finnhub_adapter import FinnhubAdapter
from market.lookup.ticker_search import TickerSearch

COMPANY = "CD Projekt"
API_KEY = os.getenv("FINNHUB_API_KEY", "")

print(f"Searching Finnhub for: {COMPANY!r} (API key: {'set' if API_KEY else 'MISSING'})")
adapter = FinnhubAdapter(API_KEY)
searcher = TickerSearch(adapter)
listings = searcher.find_listings(COMPANY)

if not listings:
    print("No listings found.")
else:
    print(f"Found {len(listings)} listing(s):")
    for lst in listings:
        print(f"  {lst.exchange}:{lst.symbol}  {lst.short_name}  [{lst.currency}]")

    first = listings[0]
    print(f"\nFetching 10 bars for {first.exchange}:{first.symbol} ...")
    records = adapter.fetch(first.symbol, first.exchange, n_bars=10)

    if not records:
        print("No OHLCV data returned.")
    else:
        print(f"Got {len(records)} bars:")
        pprint.pprint([r.model_dump() for r in records])
