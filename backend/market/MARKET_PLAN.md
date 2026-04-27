# Market — Implementation Plan

## Position in Pipeline

```
[Scuttle Crab]  →  articles.jsonl
[RKR]           →  rkr_articles.jsonl
[Tarkov]        →  firm, event, person (MySQL)
[Stage 3]       →  AML scoring, reputation_score
[Market]        →  firm_market, market_data  ← fires last
```

Market is the **final module** in the pipeline. At the point it runs, the firm record
already exists in MySQL (written by Tarkov) and AML scoring is complete. Market enriches
the firm with exchange listing info and OHLCV history, which the frontend can display
alongside the trust score.

The pipeline orchestration layer that triggers Market automatically does not exist yet.
Until it does, **Market runs as a fully standalone CLI module** — it only needs a firm
name or ID and a working database connection. No imports from RKR, Tarkov, or Stage 3.

---

## File Structure

```
backend/
└── market/
    ├── __init__.py
    ├── MARKET_PLAN.md
    ├── main.py                        # CLI entry point
    ├── config.py                      # env-based settings (TV credentials, thresholds)
    │
    ├── adapters/
    │   ├── __init__.py
    │   ├── base.py                    # ABC ExchangeAdapter: search() + fetch()
    │   └── tradingview_adapter.py     # tvdatafeed implementation
    │
    ├── lookup/
    │   ├── __init__.py
    │   └── ticker_search.py           # TickerSearch: wraps adapter, filters EQUITY only
    │
    ├── schemas/
    │   ├── __init__.py
    │   └── ohlcv.py                   # Pydantic: ListingMatch, OHLCVRecord, ChartData, FetchResult
    │
    ├── pipeline/
    │   ├── __init__.py
    │   └── fetcher.py                 # MarketFetcher: search → fetch → persist
    │
    ├── database/
    │   ├── __init__.py
    │   ├── models.py                  # SQLAlchemy ORM: FirmMarket, MarketData
    │   ├── session.py                 # SessionLocal (shared engine with Tarkov)
    │   └── repository.py             # MarketRepository: upsert_firm_market, upsert_batch
    │
    └── tests/
        ├── __init__.py
        ├── test_adapter.py
        ├── test_search.py
        ├── test_fetcher.py
        └── fixtures/
            └── sample_search_result.json
```

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `adapters/base.py` | `ExchangeAdapter` ABC with `search(name) → list[ListingMatch]` and `fetch(symbol, exchange, n_bars) → list[OHLCVRecord]` |
| `adapters/tradingview_adapter.py` | Calls `TvDatafeed.search_symbol()` for lookup and `TvDatafeed.get_hist()` for OHLCV. Maps TV exchange codes to readable names |
| `lookup/ticker_search.py` | `TickerSearch.find_listings(name)` — calls adapter, filters `quoteType == EQUITY`, deduplicates by exchange |
| `schemas/ohlcv.py` | Pydantic models for all data contracts (see below) |
| `pipeline/fetcher.py` | `MarketFetcher.fetch_company(firm_id, firm_name, days)` — orchestrates search → fetch → persist |
| `database/models.py` | SQLAlchemy ORM for `firm_market` and `market_data` tables |
| `database/repository.py` | `upsert_firm_market()` and `upsert_market_data_batch()` using `INSERT ... ON DUPLICATE KEY UPDATE` |
| `main.py` | CLI commands: `check`, `fetch`, `fetch-all` |
| `config.py` | `MarketConfig` — reads `TV_USERNAME`, `TV_PASSWORD`, `MARKET_FETCH_DAYS`, `DATABASE_URL` from env |

---

## Pydantic Schemas (schemas/ohlcv.py)

```python
class ListingMatch(BaseModel):
    tv_symbol: str      # TradingView symbol, e.g. "PKNORLEN"
    tv_exchange: str    # TradingView exchange, e.g. "GPW"
    short_name: str     # e.g. "PKN ORLEN SA"
    currency: str       # "PLN", "USD", "GBP"

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
```

---

## Data Flow (per firm)

```
MarketFetcher.fetch_company(firm_id=42, firm_name="PKN Orlen", days=365)
        │
        ▼
TickerSearch.find_listings("PKN Orlen")
        │
        ▼
TradingViewAdapter.search("PKN Orlen")
  └─ tv.search_symbol("PKN Orlen")
  └─ filter: type == "stock"
  └─ returns [ListingMatch(tv_symbol="PKNORLEN", tv_exchange="GPW", ...)]
        │
        ├─── NOT FOUND → FetchResult(found=False)  →  log + return
        │
        └─── FOUND → for each ListingMatch:
                │
                ▼
        repository.upsert_firm_market(firm_id, listing)
                │
                ▼
        TradingViewAdapter.fetch("PKNORLEN", "GPW", n_bars=365)
          └─ tv.get_hist(symbol, exchange, interval=daily, n_bars=365)
          └─ normalize DataFrame → list[OHLCVRecord]
                │
                ▼
        repository.upsert_market_data_batch(firm_id, listing, records)
          └─ INSERT INTO market_data ... ON DUPLICATE KEY UPDATE close=..., volume=...
```

---

## Adapter: TradingView (adapters/tradingview_adapter.py)

**Library:** `tvdatafeed` (unofficial, websocket-based)

**Search:**
```python
tv = TvDatafeed(username, password)   # anonymous if no credentials
results = tv.search_symbol("PKN Orlen", exchange="")
# returns list of dicts: {symbol, exchange, full_name, type, currency_code, ...}
# filter: type == "stock"
```

**Fetch OHLCV:**
```python
df = tv.get_hist(
    symbol="PKNORLEN",
    exchange="GPW",
    interval=Interval.in_daily,
    n_bars=365,
)
# DataFrame columns: open, high, low, close, volume
# Index: DatetimeIndex
```

**Exchange code mapping** (TV internal → readable):
```python
EXCHANGE_LABELS = {
    "GPW":      "GPW",
    "NASDAQ":   "NASDAQ",
    "NYSE":     "NYSE",
    "LSE":      "LSE",
    "XETRA":    "XETRA",
    "EURONEXT": "Euronext",
    "TSX":      "Toronto",
}
```

---

## Database ORM (database/models.py)

Maps to tables added in `001_initial_schema.sql`:

```python
class FirmMarket(Base):
    __tablename__ = "firm_market"
    id, firm_id, tv_symbol, tv_exchange, currency, is_active, added_at

class MarketData(Base):
    __tablename__ = "market_data"
    id, firm_id, tv_symbol, tv_exchange, date, open, high, low, close, volume, fetched_at
```

Session factory lives in `market/database/session.py` — Market owns its own engine.
It connects to the same MySQL database as Tarkov but has no Python import dependency on it.

---

## Repository (database/repository.py)

```python
class MarketRepository:
    def __init__(self, db: Session): ...

    def upsert_firm_market(self, firm_id, listing: ListingMatch) -> FirmMarket:
        # INSERT ... ON DUPLICATE KEY UPDATE is_active=TRUE

    def upsert_market_data_batch(self, firm_id, listing: ListingMatch, records: list[OHLCVRecord]) -> int:
        # Bulk upsert; returns count of rows written
        # ON DUPLICATE KEY UPDATE close, high, low, volume, fetched_at
        # (date is the natural dedupe key via UNIQUE KEY uq_firm_date)
```

---

## CLI (main.py)

```bash
# Check only — does not fetch data
python -m market.main check --company "PKN Orlen"

# Fetch chart for one firm by DB id
python -m market.main fetch --firm-id 42 --days 365

# Fetch chart by name (resolves firm_id from firm table)
python -m market.main fetch --company "CD Projekt" --days 730

# Fetch all active firms in the DB
python -m market.main fetch-all --days 90
```

`fetch-all` reads `SELECT id, full_name FROM firm` and calls `fetch_company()` for each.
Failed lookups are logged and skipped — pipeline does not crash on partial failures.

---

## Config (.env keys)

```
TV_USERNAME=          # optional — anonymous access works for most data
TV_PASSWORD=          # optional
MARKET_FETCH_DAYS=365
DATABASE_URL=mysql+pymysql://user:pass@localhost/trust_trace
```

---

## Implementation Order

1. `schemas/ohlcv.py` — Pydantic models (data contract, no deps)
2. `adapters/base.py` — ABC (no deps)
3. `adapters/tradingview_adapter.py` — TV integration + manual test
4. `lookup/ticker_search.py` — thin wrapper over adapter
5. `database/models.py` — SQLAlchemy ORM for firm_market + market_data
6. `database/session.py` — SessionLocal (reuse or reference Tarkov's)
7. `database/repository.py` — upsert methods
8. `pipeline/fetcher.py` — orchestration
9. `config.py` — env config
10. `main.py` — CLI
11. `tests/` — adapter mock + fetcher integration test

---

## Integration with AML Scoring (Stage 3)

Stage 3 Module A (Event Classifier) can enrich its score using `market_data`:

```sql
-- Price at event date and 7 days before — detect correlated drops
SELECT date, close
FROM market_data
WHERE firm_id = :firm_id
  AND date BETWEEN DATE_SUB(:event_date, INTERVAL 7 DAY) AND :event_date
ORDER BY date;
```

A price drop ≥ 10% in the window around an event date raises confidence
that the event had material market impact, which increases `risk_level`.
