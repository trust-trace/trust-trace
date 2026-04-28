from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from reasoning.schemas import MarketReasoningTrace


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
    reasoning_trace: Optional[MarketReasoningTrace] = None  # NEW: Optional reasoning trace
