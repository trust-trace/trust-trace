from __future__ import annotations

import os
import sys
from dataclasses import dataclass


_DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_DATACLASS_KWARGS)
class MarketConfig:
    database_url: str
    finnhub_api_key: str
    market_fetch_days: int

    @classmethod
    def from_env(cls) -> MarketConfig:
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
            finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
            market_fetch_days=int(os.getenv("MARKET_FETCH_DAYS", "365")),
        )
