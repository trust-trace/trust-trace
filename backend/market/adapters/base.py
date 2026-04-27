from __future__ import annotations

from abc import ABC, abstractmethod

from market.schemas.ohlcv import ListingMatch, OHLCVRecord


class ExchangeAdapter(ABC):
    @abstractmethod
    def search(self, name: str) -> list[ListingMatch]:
        """Search for listings matching the given company name."""

    @abstractmethod
    def fetch(self, symbol: str, exchange: str, n_bars: int) -> list[OHLCVRecord]:
        """Fetch OHLCV history for the given symbol/exchange."""
