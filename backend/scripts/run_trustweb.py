"""Run TrustWeb scoring on a firm and print the timeline results.

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

from tarkov.database.session import SessionLocal, init_engine, init_neo4j

from trust_web import score_firm
from trust_web.config import TrustWebConfig
from trust_web.schemas import TrustWebTimelineResult

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
    result: TrustWebTimelineResult = await score_firm(firm_id, force_rescore=True)

    print("\n" + "=" * 70)
    print("TRUSTWEB TIMELINE RESULT")
    print("=" * 70)
    print(f"  Firm ID:      {firm_id}")
    print(f"  Computed At:  {result.computed_at}")
    print()

    print(f"  {'Bucket':<8} {'Period':<24} {'Score':>7}  {'Nodes':>5}  {'Edges':>5}")
    print("  " + "─" * 60)
    for e in result.entries:
        period = f"{e.bucket_start.strftime('%Y-%m')} → {e.bucket_end.strftime('%Y-%m')}"
        print(f"  T{e.bucket_index:<7} {period:<24} {e.score:>7.3f}  {e.node_count:>5}  {e.edge_count:>5}")

    print()
    print("  Explanation:")
    for line in (result.explanation or "").split("\n"):
        print(f"    {line}")

    print("=" * 70)


if __name__ == "__main__":
    firm_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(firm_id))
