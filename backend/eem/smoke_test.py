"""
EEM smoke test — run with:
    python -m eem.smoke_test

What it does:
  1. Connects to the DB from DATABASE_URL in .env
  2. Creates EEM tables if they don't exist
  3. Wipes any leftover data from previous runs of this script
  4. Inserts a mock firm + 4 classical events with sources and people
  5. Calls enrich_firm() — the public EEM entry point
  6. Prints the score and every enriched event
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import select, text

load_dotenv()

import eem.config as config

if not config.DATABASE_URL:
    print("ERROR: DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)
if not config.OPENROUTER_API_KEY:
    print("ERROR: EEM_API_KEY (or LLM_API_KEY) is not set", file=sys.stderr)
    sys.exit(1)

from eem.database.models import EventEnrichment, FirmScore
from eem.database.session import get_db, init_engine

# ── bootstrap ──────────────────────────────────────────────────────────────────
# Tables must already exist — run `python create_db.py` once on a fresh Postgres.
init_engine(config.DATABASE_URL)

# ── mock data ──────────────────────────────────────────────────────────────────
FIRM_SENTINEL_NAME = "Jastrzębska Spółka Węglowa S.A. [SMOKE TEST]"

MOCK_FIRM = {
    "full_name": FIRM_SENTINEL_NAME,
    "country": "PL",
}

MOCK_EVENTS = [
    {
        "id": str(uuid.uuid4()),
        "title": "CBA zatrzymało trzech członków zarządu spółki",
        "event_type": "corruption",
        "risk_level": 9,
        "occurred_at": datetime(2024, 3, 15, 8, 14),
        "source_text_quote": "Funkcjonariusze CBA przeprowadzili akcję w siedzibie spółki. Zatrzymanym przedstawiono zarzuty przyjęcia korzyści majątkowej w łącznej kwocie ponad 4,2 mln zł.",
        "sources": [
            {
                "url": "https://rzeczpospolita.pl/art/cba-jsw-2024",
                "title": "Rzeczpospolita",
                "content": "Funkcjonariusze Centralnego Biura Antykorupcyjnego przeprowadzili w czwartek rano zakrojoną na szeroką skalę akcję w siedzibie spółki w Jastrzębiu-Zdroju. Zatrzymanym przedstawiono zarzuty przyjęcia korzyści majątkowej w łącznej kwocie ponad 4,2 mln zł oraz działania na szkodę spółki Skarbu Państwa. Śledztwo prowadzi Prokuratura Regionalna w Katowicach.",
                "published_at": datetime(2024, 3, 15, 9, 0),
                "credibility": 0.95,
            },
            {
                "url": "https://parkiet.com/art/jsw-areszty-2024",
                "title": "Parkiet",
                "content": "Spółka poinformowała o zatrzymaniu przez CBA trzech członków zarządu w związku z zarzutami korupcji. Kurs akcji JSW spadł o 11% w pierwszych minutach handlu.",
                "published_at": datetime(2024, 3, 15, 10, 30),
                "credibility": 0.92,
            },
        ],
        "people": [
            {"name": "Marek Wiśniewski", "role": "Prezes Zarządu", "role_in_event": "główny podejrzany"},
            {"name": "Tomasz Kowalczyk", "role": "CFO", "role_in_event": "podejrzany"},
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Spółka oskarżona o pranie pieniędzy w transakcjach z podmiotami rosyjskimi",
        "event_type": "money_laundering",
        "risk_level": 8,
        "occurred_at": datetime(2024, 1, 10, 10, 0),
        "source_text_quote": "Prokuratura postawiła zarzuty spółce w związku z podejrzanymi transferami środków do podmiotów rosyjskich na łączną kwotę 230 mln zł.",
        "sources": [
            {
                "url": "https://gazeta.pl/art/jsw-pranie-pieniedzy",
                "title": "Gazeta Wyborcza Biznes",
                "content": "Prokuratura Krajowa poinformowała o postawieniu zarzutów prania pieniędzy wobec spółki i kilku jej byłych menedżerów. Chodzi o serię transakcji przeprowadzonych w latach 2021–2023, w których środki miały trafiać do podmiotów powiązanych z rosyjskimi oligarchami.",
                "published_at": datetime(2024, 1, 10, 11, 0),
                "credibility": 0.9,
            },
        ],
        "people": [
            {"name": "Anna Jabłońska", "role": "Dyrektor Finansowy", "role_in_event": "podejrzana"},
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "title": "KNF wszczyna postępowanie wyjaśniające wobec spółki ws. manipulacji informacją",
        "event_type": "regulatory_action",
        "risk_level": 6,
        "occurred_at": datetime(2023, 11, 5, 14, 0),
        "source_text_quote": "Komisja Nadzoru Finansowego wszczęła postępowanie wyjaśniające w związku z podejrzeniem naruszenia obowiązków informacyjnych.",
        "sources": [
            {
                "url": "https://pulsbizneu.pl/art/knf-jsw-postepowanie",
                "title": "Puls Biznesu",
                "content": "KNF potwierdziła wszczęcie postępowania wobec spółki w związku z podejrzeniem, że zarząd celowo opóźniał publikację informacji poufnych dotyczących wyniku finansowego za Q3 2023. Grozi kara do 10 mln zł.",
                "published_at": datetime(2023, 11, 5, 15, 0),
                "credibility": 0.88,
            },
        ],
        "people": [],
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Spółka podpisała kontrakt na modernizację infrastruktury wydobywczej — 380 mln zł",
        "event_type": "investment",
        "risk_level": 2,
        "occurred_at": datetime(2023, 8, 20, 10, 0),
        "source_text_quote": "Zarząd spółki poinformował o podpisaniu umowy z konsorcjum FAMUR-Kopex na modernizację systemów wentylacji i transportu w trzech kopalniach.",
        "sources": [
            {
                "url": "https://bankier.pl/art/jsw-modernizacja-2023",
                "title": "Bankier.pl",
                "content": "Zarząd Jastrzębskiej Spółki Węglowej poinformował o podpisaniu znaczącej umowy inwestycyjnej. Kontrakt opiewa na 380 mln zł i obejmuje modernizację trzech kopalni. Inwestycja ma poprawić bezpieczeństwo i efektywność wydobycia.",
                "published_at": datetime(2023, 8, 20, 11, 0),
                "credibility": 0.8,
            },
        ],
        "people": [],
    },
]


# ── helpers ────────────────────────────────────────────────────────────────────

def _wipe_previous_run(db) -> None:
    """Remove rows from a previous smoke-test run, identified by the sentinel firm name."""
    row = db.execute(
        text("SELECT id FROM firm WHERE full_name = :name"),
        {"name": FIRM_SENTINEL_NAME},
    ).fetchone()
    if row is None:
        return
    fid = row.id
    db.execute(text("DELETE FROM person_event WHERE event_id IN (SELECT unique_id FROM event WHERE firm_id = :fid)"), {"fid": fid})
    db.execute(text("DELETE FROM source       WHERE event_id IN (SELECT unique_id FROM event WHERE firm_id = :fid)"), {"fid": fid})
    db.execute(text("DELETE FROM event_enrichment WHERE event_id IN (SELECT unique_id FROM event WHERE firm_id = :fid)"), {"fid": fid})
    db.execute(text("DELETE FROM firm_score WHERE firm_id = :fid"), {"fid": fid})
    db.execute(text("DELETE FROM event  WHERE firm_id = :fid"), {"fid": fid})
    db.execute(text("DELETE FROM person WHERE firm_id = :fid"), {"fid": fid})
    db.execute(text("DELETE FROM firm_alias WHERE firm_id = :fid"), {"fid": fid})
    db.execute(text("DELETE FROM firm  WHERE id = :fid"), {"fid": fid})
    db.commit()
    print(f"[setup] Cleared previous smoke-test data for firm_id={fid}")


def _insert_mock_data(db) -> int:
    """Insert the mock firm and events; return the new firm_id."""
    result = db.execute(
        text(
            "INSERT INTO firm (full_name, country, created_at, updated_at) "
            "VALUES (:name, :country, :now, :now) RETURNING id"
        ),
        {"name": MOCK_FIRM["full_name"], "country": MOCK_FIRM["country"], "now": datetime.utcnow()},
    )
    firm_id = result.fetchone().id

    for ev in MOCK_EVENTS:
        db.execute(
            text(
                "INSERT INTO event (unique_id, firm_id, title, event_type, event_category, "
                "risk_level, occurred_at, extraction_confidence, source_text_quote, created_at) "
                "VALUES (:uid, :fid, :title, :etype, 'classical', :rlevel, :oat, 0.85, :quote, :now)"
            ),
            {
                "uid": ev["id"], "fid": firm_id, "title": ev["title"],
                "etype": ev["event_type"], "rlevel": ev["risk_level"],
                "oat": ev["occurred_at"], "quote": ev["source_text_quote"], "now": datetime.utcnow(),
            },
        )
        for src in ev["sources"]:
            db.execute(
                text(
                    "INSERT INTO source (event_id, url, title, content, language, "
                    "source_type, source_category, published_at, credibility, created_at) "
                    "VALUES (:eid, :url, :title, :content, 'pl', 'original', 'article', :pub, :cred, :now)"
                ),
                {
                    "eid": ev["id"], "url": src["url"], "title": src["title"],
                    "content": src["content"], "pub": src["published_at"],
                    "cred": src["credibility"], "now": datetime.utcnow(),
                },
            )
        for person in ev["people"]:
            result = db.execute(
                text(
                    "INSERT INTO person (name, role, firm_id, created_at, updated_at) "
                    "VALUES (:name, :role, :fid, :now, :now) RETURNING id"
                ),
                {"name": person["name"], "role": person["role"], "fid": firm_id, "now": datetime.utcnow()},
            )
            person_id = result.fetchone().id
            db.execute(
                text(
                    "INSERT INTO person_event (person_id, event_id, role_in_event, confidence, created_at) "
                    "VALUES (:pid, :eid, :role, 0.9, :now)"
                ),
                {"pid": person_id, "eid": ev["id"], "role": person["role_in_event"], "now": datetime.utcnow()},
            )

    db.commit()
    print(f"[setup] Inserted firm_id={firm_id} with {len(MOCK_EVENTS)} events")
    return firm_id


def _print_results(db, firm_id: int, score: float) -> None:
    print()
    print("=" * 60)
    print(f"  FIRM SCORE:  {score:.1f} / 100")
    print("=" * 60)

    firm_score = db.execute(
        select(FirmScore).where(FirmScore.firm_id == firm_id)
    ).scalar_one_or_none()

    if firm_score:
        print(f"  risk:        {firm_score.risk}")
        print(f"  trend:       {firm_score.trend:+d}")
        print(f"  history:     {json.loads(firm_score.score_history)}")
        print(f"  keywords:    {json.loads(firm_score.keywords)}")

    print()

    enrichments = db.execute(
        text(
            "SELECT e.title, e.event_type, e.risk_level, e.occurred_at, "
            "       ee.sentiment, ee.impact, ee.source_tier, ee.keywords, ee.excerpt, ee.entities "
            "FROM event_enrichment ee "
            "JOIN event e ON e.unique_id = ee.event_id "
            "WHERE e.firm_id = :fid "
            "ORDER BY e.occurred_at ASC"
        ),
        {"fid": firm_id},
    ).fetchall()

    print(f"  ENRICHED EVENTS ({len(enrichments)}/{len(MOCK_EVENTS)}):")
    print()
    for i, row in enumerate(enrichments, 1):
        print(f"  [{i}] {row.title}")
        print(f"       type={row.event_type}  risk_level={row.risk_level}  date={row.occurred_at.date()}")
        print(f"       sentiment={row.sentiment:+.2f}  impact={row.impact:+.1f}  tier={row.source_tier}")
        print(f"       keywords={json.loads(row.keywords)}")
        print(f"       entities={json.loads(row.entities)}")
        print(f"       excerpt: {row.excerpt}")
        print()


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[config] model={config.EEM_MODEL}")
    print(f"[config] db={config.DATABASE_URL.split('@')[-1]}")  # hide credentials
    print()

    with get_db() as db:
        _wipe_previous_run(db)
        firm_id = _insert_mock_data(db)

    print(f"[eem] calling enrich_firm({firm_id}) ...")
    print()

    from eem import enrich_firm
    score = enrich_firm(firm_id)

    with get_db() as db:
        _print_results(db, firm_id, score)


if __name__ == "__main__":
    main()
