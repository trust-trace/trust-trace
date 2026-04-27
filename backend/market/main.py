"""CLI entry point for the Market module.

Usage:
    python -m market.main check --company "PKN Orlen"
    python -m market.main fetch --firm-id 42 --days 365
    python -m market.main fetch --company "CD Projekt" --days 730
    python -m market.main fetch-all --days 90
"""
from __future__ import annotations

import argparse
import logging
import sys

from market.adapters.finnhub_adapter import FinnhubAdapter
from market.config import MarketConfig
from market.database.session import create_all, get_db, init_engine
from market.lookup.ticker_search import TickerSearch
from market.pipeline.fetcher import MarketFetcher

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("market")


def _build_fetcher(cfg: MarketConfig, db) -> MarketFetcher:
    adapter = FinnhubAdapter(cfg.finnhub_api_key)
    return MarketFetcher(adapter, db)


def cmd_check(args: argparse.Namespace, cfg: MarketConfig) -> None:
    adapter = FinnhubAdapter(cfg.finnhub_api_key)
    searcher = TickerSearch(adapter)
    listings = searcher.find_listings(args.company)
    if not listings:
        print(f"No listings found for: {args.company!r}")
        sys.exit(1)
    for lst in listings:
        print(f"  {lst.exchange}:{lst.symbol}  {lst.short_name}  [{lst.currency}]")


def cmd_fetch(args: argparse.Namespace, cfg: MarketConfig) -> None:
    init_engine(cfg.database_url)
    create_all()

    days = args.days or cfg.market_fetch_days

    with get_db() as db:
        fetcher = _build_fetcher(cfg, db)

        if args.firm_id:
            result = fetcher.fetch_company(args.firm_id, _resolve_name(db, args.firm_id), days)
        else:
            firm_id, firm_name = _resolve_by_name(db, args.company)
            result = fetcher.fetch_company(firm_id, firm_name, days)

    if not result.found:
        print(f"No listing found for {result.firm_name!r}")
        sys.exit(1)

    for chart in result.charts:
        print(f"  {chart.listing.exchange}:{chart.listing.symbol}  {len(chart.records)} bars")


def cmd_fetch_all(args: argparse.Namespace, cfg: MarketConfig) -> None:
    init_engine(cfg.database_url)
    create_all()

    days = args.days or cfg.market_fetch_days

    with get_db() as db:
        firms = db.execute(
            __import__("sqlalchemy").text("SELECT id, full_name FROM firm")
        ).fetchall()

        if not firms:
            logger.warning("No firms found in database.")
            return

        fetcher = _build_fetcher(cfg, db)
        ok = 0
        for firm_id, firm_name in firms:
            try:
                result = fetcher.fetch_company(firm_id, firm_name, days)
                if result.found:
                    ok += 1
            except Exception as exc:
                logger.error("Failed for firm_id=%d %r: %s", firm_id, firm_name, exc)

    print(f"Done: {ok}/{len(firms)} firms enriched.")


def _resolve_name(db, firm_id: int) -> str:
    import sqlalchemy
    row = db.execute(
        sqlalchemy.text("SELECT full_name FROM firm WHERE id = :id"), {"id": firm_id}
    ).fetchone()
    if row is None:
        print(f"Firm id={firm_id} not found in database.")
        sys.exit(1)
    return row[0]


def _resolve_by_name(db, name: str) -> tuple[int, str]:
    import sqlalchemy
    row = db.execute(
        sqlalchemy.text("SELECT id, full_name FROM firm WHERE full_name ILIKE :name LIMIT 1"),
        {"name": f"%{name}%"},
    ).fetchone()
    if row is None:
        print(f"Firm {name!r} not found in database.")
        sys.exit(1)
    return row[0], row[1]


def main() -> None:
    cfg = MarketConfig.from_env()

    parser = argparse.ArgumentParser(prog="market")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Search listings without persisting")
    p_check.add_argument("--company", required=True)

    p_fetch = sub.add_parser("fetch", help="Fetch OHLCV for one firm")
    p_fetch.add_argument("--firm-id", type=int)
    p_fetch.add_argument("--company")
    p_fetch.add_argument("--days", type=int)

    p_all = sub.add_parser("fetch-all", help="Fetch OHLCV for all firms in DB")
    p_all.add_argument("--days", type=int)

    args = parser.parse_args()

    if args.command == "check":
        cmd_check(args, cfg)
    elif args.command == "fetch":
        if not args.firm_id and not args.company:
            parser.error("fetch requires --firm-id or --company")
        cmd_fetch(args, cfg)
    elif args.command == "fetch-all":
        cmd_fetch_all(args, cfg)


if __name__ == "__main__":
    main()
