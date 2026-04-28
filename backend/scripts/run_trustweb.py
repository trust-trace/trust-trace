"""Run TrustWeb scoring on a firm and print the results.

Usage:
    cd backend && python -m scripts.run_trustweb [firm_id]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text

from tarkov.database.session import SessionLocal, init_engine, init_neo4j

from trust_web import score_firm
from trust_web.config import TrustWebConfig

PG_URL = "postgresql+psycopg2://trusttrace:trusttrace@localhost:5432/trusttrace_db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("run_trustweb")


async def main(firm_id: int):
    logger.info("Initializing connections...")
    init_engine(PG_URL)

    config = TrustWebConfig.from_env()
    init_neo4j(config.neo4j_uri, config.neo4j_user, config.neo4j_password)

    logger.info("Scoring firm %d ...", firm_id)
    risk_score = await score_firm(firm_id, force_rescore=True)

    print("\n" + "=" * 60)
    print("TRUSTWEB RESULT")
    print("=" * 60)
    print(f"  Firm ID:      {firm_id}")
    print(f"  Risk Score:   {risk_score:.4f}")

    # Read the persisted row for the full details
    session = SessionLocal()
    try:
        row = session.execute(
            text(
                "SELECT node_count, edge_count, max_depth_used, explanation, computed_at "
                "FROM trustweb_score WHERE firm_id = :fid "
                "ORDER BY computed_at DESC LIMIT 1"
            ),
            {"fid": firm_id},
        ).first()
        if row:
            print(f"  Nodes:        {row.node_count}")
            print(f"  Edges:        {row.edge_count}")
            print(f"  Max Depth:    {row.max_depth_used}")
            print(f"  Computed At:  {row.computed_at}")
            print()
            print("  Explanation:")
            for line in (row.explanation or "").split("\n"):
                print(f"    {line}")
    finally:
        session.close()

    print("=" * 60)


if __name__ == "__main__":
    firm_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(firm_id))
