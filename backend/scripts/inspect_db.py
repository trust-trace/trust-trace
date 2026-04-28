#!/usr/bin/env python3
"""Dump every table in the Postgres database to the console.

Usage:
    cd backend && python -m scripts.inspect_db
    cd backend && python -m scripts.inspect_db --table firm --table event
    cd backend && python -m scripts.inspect_db --limit 5
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import argparse

from sqlalchemy import create_engine, inspect, text


DEFAULT_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://trusttrace:trusttrace@localhost:5432/trusttrace_db",
)

SKIP_TABLES = {"alembic_version", "pg_stat_statements"}


def _fmt_value(val, max_len: int = 80) -> str:
    if val is None:
        return "NULL"
    s = str(val)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def dump_table(engine, table_name: str, limit: int | None) -> int:
    with engine.connect() as conn:
        q = f'SELECT * FROM "{table_name}"'
        if limit:
            q += f" LIMIT {limit}"
        rows = conn.execute(text(q)).fetchall()
        if not rows:
            print(f"\n{'─'*60}")
            print(f"  {table_name}  (empty)")
            print(f"{'─'*60}")
            return 0

        keys = list(rows[0]._mapping.keys())

        col_widths = {k: len(k) for k in keys}
        str_rows: list[dict[str, str]] = []
        for row in rows:
            d = {}
            for k in keys:
                s = _fmt_value(row._mapping[k])
                d[k] = s
                col_widths[k] = max(col_widths[k], len(s))
            str_rows.append(d)

        total_width = sum(col_widths.values()) + 3 * (len(keys) - 1) + 4
        if total_width > 220:
            for k in col_widths:
                col_widths[k] = min(col_widths[k], 40)

        header = " | ".join(k.ljust(col_widths[k]) for k in keys)
        sep = "-+-".join("-" * col_widths[k] for k in keys)

        print(f"\n{'━'*60}")
        print(f"  {table_name}  ({len(rows)} row{'s' if len(rows) != 1 else ''})")
        print(f"{'━'*60}")
        print(f"  {header}")
        print(f"  {sep}")
        for d in str_rows:
            line = " | ".join(d[k].ljust(col_widths[k])[:col_widths[k]] for k in keys)
            print(f"  {line}")

        return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Dump Postgres tables to console")
    parser.add_argument("--url", default=DEFAULT_URL, help="Postgres connection URL")
    parser.add_argument("--table", dest="tables", action="append", default=[], help="Only dump these tables (repeatable)")
    parser.add_argument("--limit", default=None, type=int, help="Max rows per table")
    parser.add_argument("--counts-only", action="store_true", help="Just print row counts")
    args = parser.parse_args()

    url = args.url
    tables = args.tables
    limit = args.limit
    counts_only = args.counts_only

    engine = create_engine(url)
    inspector = inspect(engine)

    all_tables = sorted(inspector.get_table_names())
    if tables:
        all_tables = [t for t in all_tables if t in tables]

    if not all_tables:
        print("No tables found.")
        return

    print(f"\n  Database: {url.split('@')[-1] if '@' in url else url}")
    print(f"  Tables:   {len(all_tables)}")

    if counts_only:
        print(f"\n  {'Table':<35} {'Rows':>8}")
        print(f"  {'─'*35} {'─'*8}")
        total = 0
        with engine.connect() as conn:
            for t in all_tables:
                if t in SKIP_TABLES:
                    continue
                try:
                    n = conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
                except Exception:
                    n = "?"
                total += n if isinstance(n, int) else 0
                print(f"  {t:<35} {n:>8}")
        print(f"  {'─'*35} {'─'*8}")
        print(f"  {'TOTAL':<35} {total:>8}")
        return

    grand_total = 0
    for t in all_tables:
        if t in SKIP_TABLES:
            continue
        try:
            grand_total += dump_table(engine, t, limit)
        except Exception as exc:
            print(f"\n  ⚠ {t}: {exc}")

    print(f"\n{'━'*60}")
    print(f"  Total: {grand_total} rows across {len(all_tables)} tables")
    print(f"{'━'*60}\n")


if __name__ == "__main__":
    main()
