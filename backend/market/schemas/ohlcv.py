from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ListingMatch(BaseModel):
    symbol: str       # e.g. "PKN.WA", "AAPL"
    exchange: str     # MIC code, e.g. "XWAR", "XNAS"
    short_name: str
    currency: str


class OHLCVRecord(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartData(BaseModel):
    listing: ListingMatch
    records: list[OHLCVRecord]


class FetchResult(BaseModel):
    firm_id: int
    firm_name: str
    found: bool
    charts: list[ChartData]
    reasoning_trace_id: Optional[int] = None  # NEW: ID to reasoning trace in database
