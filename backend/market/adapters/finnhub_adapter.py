from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta

import finnhub

from market.adapters.base import ExchangeAdapter
from market.schemas.ohlcv import ListingMatch, OHLCVRecord

logger = logging.getLogger(__name__)

EQUITY_TYPES = {"Common Stock", "ADR", "GDR"}


class FinnhubAdapter(ExchangeAdapter):
    def __init__(self, api_key: str) -> None:
        self._client = finnhub.Client(api_key=api_key)

    def search(self, name: str) -> list[ListingMatch]:
        try:
            result = self._client.symbol_lookup(name)
        except Exception as exc:
            logger.warning("Finnhub search failed for %r: %s", name, exc)
            return []

        listings: list[ListingMatch] = []
        for item in result.get("result", []):
            if item.get("type") not in EQUITY_TYPES:
                continue
            symbol = item["symbol"]
            # Finnhub encodes the exchange as the suffix after "." (e.g. CDR.WA → WA, AAPL → US)
            parts = symbol.rsplit(".", 1)
            exchange = parts[1] if len(parts) == 2 else "US"
            listings.append(
                ListingMatch(
                    symbol=symbol,
                    exchange=exchange,
                    short_name=item.get("description", ""),
                    currency="",
                )
            )
        return listings

    def fetch(self, symbol: str, exchange: str, n_bars: int) -> list[OHLCVRecord]:
        to_ts = int(time.time())
        from_ts = int((datetime.utcnow() - timedelta(days=n_bars)).timestamp())

        try:
            data = self._client.stock_candles(symbol, "D", from_ts, to_ts)
        except Exception as exc:
            logger.warning("Finnhub candles failed for %s: %s", symbol, exc)
            return []

        if not data or data.get("s") != "ok":
            logger.info("No candle data for %s (status=%s)", symbol, data.get("s") if data else "none")
            return []

        records: list[OHLCVRecord] = []
        for i, ts in enumerate(data["t"]):
            d = date.fromtimestamp(ts)
            records.append(
                OHLCVRecord(
                    date=d,
                    open=float(data["o"][i]),
                    high=float(data["h"][i]),
                    low=float(data["l"][i]),
                    close=float(data["c"][i]),
                    volume=int(data["v"][i]),
                )
            )
        return records
