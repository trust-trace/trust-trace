from __future__ import annotations

from market.adapters.base import ExchangeAdapter
from market.schemas.ohlcv import ListingMatch


class TickerSearch:
    def __init__(self, adapter: ExchangeAdapter) -> None:
        self._adapter = adapter

    def find_listings(self, name: str) -> list[ListingMatch]:
        """Return EQUITY listings for *name*, deduplicated by exchange."""
        all_listings = self._adapter.search(name)

        seen: set[str] = set()
        unique: list[ListingMatch] = []
        for listing in all_listings:
            key = listing.exchange
            if key not in seen:
                seen.add(key)
                unique.append(listing)
        return unique
