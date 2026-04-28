#!/usr/bin/env python3
"""Clear all data from Postgres (and optionally Neo4j).

Usage:
    cd backend && python -m scripts.clear_db
    cd backend && python -m scripts.clear_db --table firm --table event
    cd backend && python -m scripts.clear_db --keep-schema
    cd backend && python -m scripts.clear_db --neo4j
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import create_engine, inspect, text

DEFAULT_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://trusttrace:trusttrace@localhost:5432/trusttrace_db",
)

# Order matters: children before parents to respect FK constraints
DROP_ORDER = [
    "final_score_timeline",
    "pipeline_run",
    "trustweb_run",
    "trustweb_score_timeline",
    "trustweb_score",
    "firm_score_timeline",
    "event_enrichment",
    "firm_score",
    "sentiment_keywords",
    "sentiment",
    "market_data",
    "firm_market",
    "reputation_score",
    "connection_entity",
    "person_event",
    "source",
    "person",
    "event",
    "firm_alias",
    "rkr_scoring",
    "risk_keywords",
    "article_metadata",
    "ingestion_job",
    "firm",
]


def truncate_tables(engine, tables: list[str]) -> int:
    cleared = 0
    with engine.connect() as conn:
        all_tables = set(inspect(engine).get_table_names())
        for t in tables:
            if t not in all_tables:
                continue
            count = conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
            if count == 0:
                print(f"  {t:<40} (already empty)")
                continue
            conn.execute(text(f'TRUNCATE TABLE "{t}" CASCADE'))
            print(f"  {t:<40} {count} rows deleted")
            cleared += count
        conn.commit()
    return cleared


def drop_all_tables(engine) -> int:
    dropped = 0
    with engine.connect() as conn:
        all_tables = set(inspect(engine).get_table_names())
        for t in DROP_ORDER:
            if t in all_tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
                print(f"  {t:<40} dropped")
                dropped += 1
        remaining = all_tables - set(DROP_ORDER)
        for t in sorted(remaining):
            conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
            print(f"  {t:<40} dropped")
            dropped += 1
        conn.commit()
    return dropped


def clear_neo4j():
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "trusttrace")

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS c").single()
        count = result["c"]
        session.run("MATCH (n) DETACH DELETE n")
    driver.close()
    print(f"  Neo4j: {count} nodes deleted")


def main():
    parser = argparse.ArgumentParser(description="Clear Postgres (and optionally Neo4j) data")
    parser.add_argument("--url", default=DEFAULT_URL, help="Postgres connection URL")
    parser.add_argument("--table", dest="tables", action="append", default=[], help="Only clear these tables (repeatable)")
    parser.add_argument("--drop", action="store_true", help="DROP tables instead of TRUNCATE")
    parser.add_argument("--neo4j", action="store_true", help="Also clear Neo4j graph")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    db_label = args.url.split("@")[-1] if "@" in args.url else args.url
    action = "DROP" if args.drop else "TRUNCATE"
    scope = ", ".join(args.tables) if args.tables else "ALL tables"

    print(f"\n  Database: {db_label}")
    print(f"  Action:   {action} {scope}")
    if args.neo4j:
        print(f"  Neo4j:    will be cleared too")

    if not args.yes:
        confirm = input("\n  Are you sure? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Aborted.")
            return

    print()
    engine = create_engine(args.url)

    if args.drop and not args.tables:
        dropped = drop_all_tables(engine)
        print(f"\n  Done — {dropped} tables dropped.")
    else:
        tables = args.tables if args.tables else DROP_ORDER
        cleared = truncate_tables(engine, tables)
        print(f"\n  Done — {cleared} rows cleared.")

    if args.neo4j:
        print()
        try:
            clear_neo4j()
        except Exception as exc:
            print(f"  Neo4j error: {exc}")

    print()


if __name__ == "__main__":
    main()
