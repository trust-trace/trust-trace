#!/usr/bin/env python
"""
Full pipeline demo — seeds test data, runs EEM + NSA, then prints all reasoning traces.

Usage:  cd backend && python run_traces_demo.py
No LLM key needed: EEM falls back to deterministic analysis.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = BACKEND_DIR / "test_traces.db"
DB_URL   = f"sqlite+pysqlite:///{DB_PATH}"

# Must be set before eem.config is imported (it calls load_dotenv at import time)
os.environ["DATABASE_URL"] = DB_URL
os.environ["EEM_API_KEY"]  = ""   # empty key → deterministic fallback

# ── engine init ───────────────────────────────────────────────────────────────
# Order matters: import models BEFORE create_all so they register on their Base

from tarkov.database.session  import Base as TarkovBase,  init_engine as tarkov_init,  SessionLocal as TarkovSessionFactory
from eem.database.session      import Base as EEMBase,     init_engine as eem_init
from reasoning.session         import Base as ReasoningBase, init_engine as reasoning_init, SessionLocal as ReasoningSessionFactory

import nsa.database.models      # registers NSA ORM models onto TarkovBase
import reasoning.models         # registers ReasoningTraceModel onto ReasoningBase

# Wipe + recreate the DB file for a clean run
if DB_PATH.exists():
    DB_PATH.unlink()
    print(f"[DB] Removed old {DB_PATH.name}")

tarkov_engine   = tarkov_init(DB_URL)
eem_engine      = eem_init(DB_URL)
reasoning_engine = reasoning_init(DB_URL)

TarkovBase.metadata.create_all(bind=tarkov_engine)
EEMBase.metadata.create_all(bind=eem_engine)
ReasoningBase.metadata.create_all(bind=reasoning_engine)
print(f"[DB] Created {DB_PATH.name}")

# ── seed test data ────────────────────────────────────────────────────────────
from tarkov.database.models import Event, Firm, Person, PersonEvent, Source

db = TarkovSessionFactory()

firm = Firm(full_name="Acme Corp", country="PL")
db.add(firm)
db.flush()
firm_id = firm.id

base_time = datetime(2025, 6, 1)
events_seed = [
    ("fraud",             "Fraud allegations against Acme Corp CEO",          8, base_time),
    ("money_laundering",  "Suspicious transactions flagged at Acme Corp",      9, base_time + timedelta(days=30)),
    ("regulatory_action", "KNF launches formal inquiry into Acme Corp",        7, base_time + timedelta(days=60)),
]

event_ids: list[str] = []
for etype, title, risk, occurred in events_seed:
    eid = str(uuid.uuid4())
    db.add(Event(
        unique_id=eid,
        firm_id=firm_id,
        event_type=etype,
        event_category="classical",
        title=title,
        risk_level=risk,
        occurred_at=occurred,
        extraction_confidence=0.85,
        source_text_quote=f"Reported: {title}.",
    ))
    db.add(Source(
        event_id=eid,
        url=f"https://news.example.com/{etype}-acme",
        title=f"Report: {title}",
        content=(
            f"Full investigative report on {title}. "
            "Prokuratura wszczęła postępowanie. KNF i CBA prowadzą śledztwo. "
            "Podejrzenia o korupcję i pranie pieniędzy są poważne."
        ),
        language="pl",
        source_type="news",
        credibility=0.8,
        published_at=occurred,
    ))
    event_ids.append(eid)

people_seed = [("John Smith", "CEO"), ("Jane Doe", "CFO")]
person_ids: list[int] = []
for name, role in people_seed:
    p = Person(name=name, role=role, firm_id=firm_id)
    db.add(p)
    db.flush()
    person_ids.append(p.id)
    for eid in event_ids[:2]:
        db.add(PersonEvent(person_id=p.id, event_id=eid, role_in_event=role, confidence=0.85))

db.commit()
print(f"[SEED] firm_id={firm_id}  events={len(events_seed)}  people={len(people_seed)}")

# ── EEM ───────────────────────────────────────────────────────────────────────
print("\n[EEM] Running enrichment pipeline (deterministic fallback)…")
from eem._pipeline import _run as eem_run

try:
    timeline = eem_run(firm_id)
    latest   = timeline[-1]
    print(f"[EEM] Done — {len(timeline)} buckets | latest score={latest.score} risk={latest.risk}")
except Exception as exc:
    print(f"[EEM] ERROR: {exc}", file=sys.stderr)
    import traceback; traceback.print_exc()

# ── NSA ───────────────────────────────────────────────────────────────────────
print("\n[NSA] Running scoring pipeline with mock fetchers…")

from nsa.database.repository import NsaRepository
from nsa.fetchers.base import BasePersonFetcher, FetchOutcome
from nsa.schemas.domain import PersonEvidence
from nsa.scoring.service import NSAService


class _MockSanctionsFetcher(BasePersonFetcher):
    source_kind = "sanctions"

    def fetch(self, person, company_context) -> FetchOutcome:
        if "Smith" in person.name:
            return FetchOutcome(
                person_id=person.id,
                evidence=(PersonEvidence(
                    source_kind="sanctions",
                    source_url="https://sanctions.example.com/john-smith",
                    title="John Smith — OFAC SDN List",
                    excerpt="Subject appears on OFAC Specially Designated Nationals list.",
                    severity=0.9,
                    confidence=0.95,
                    claim_type="sanctions_hit",
                ),),
            )
        return FetchOutcome(person_id=person.id, evidence=())


class _MockNewsFetcher(BasePersonFetcher):
    source_kind = "news"

    def fetch(self, person, company_context) -> FetchOutcome:
        slug = person.name.lower().replace(" ", "-")
        return FetchOutcome(
            person_id=person.id,
            evidence=(PersonEvidence(
                source_kind="news",
                source_url=f"https://news.example.com/{slug}-fraud",
                title=f"{person.name} linked to Acme Corp fraud investigation",
                excerpt=f"{person.name} is named in the ongoing fraud investigation at Acme Corp.",
                severity=0.6,
                confidence=0.7,
                claim_type="fraud_allegation",
            ),),
        )


nsa_db  = TarkovSessionFactory()
nsa_svc = NSAService(
    repository=NsaRepository(nsa_db),
    fetchers=[_MockSanctionsFetcher(), _MockNewsFetcher()],
)

try:
    nsa_result = nsa_svc.score_company(
        firm_id=firm_id,
        correlation_id="demo-corr-001",
        db_session=nsa_db,
        include_reasoning=True,
    )
    print(f"[NSA] Done — company_risk={nsa_result.company_risk_score:.3f}  people_scored={nsa_result.people_scored}")
    for s in (nsa_result.people_summaries or []):
        print(f"[NSA]   {s.person_name}: risk={s.risk_score:.3f}")
except Exception as exc:
    print(f"[NSA] ERROR: {exc}", file=sys.stderr)
    import traceback; traceback.print_exc()
finally:
    nsa_db.close()

# ── display traces ────────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("REASONING TRACES")
print("=" * 72)

from reasoning.storage import ReasoningTraceRepository

trace_db = ReasoningSessionFactory()
repo     = ReasoningTraceRepository(trace_db)

total = 0
for classifier in ("EEM", "NSA", "Tarkov", "Market"):
    traces = repo.get_by_classifier(classifier, limit=50)
    if not traces:
        continue
    total += len(traces)
    print(f"\n{'─'*72}")
    print(f"  {classifier}  ({len(traces)} trace{'s' if len(traces) != 1 else ''})")
    print(f"{'─'*72}")
    for t in traces:
        eid = t.entity_id
        print(f"\n  entity_type : {t.entity_type}")
        print(f"  entity_id   : {eid[:36]}")
        print(f"  created_at  : {t.created_at.isoformat()}")
        print(f"  trace_data  :")
        lines = json.dumps(t.trace_data, indent=4, ensure_ascii=False).splitlines()
        for line in lines:
            print(f"    {line}")

trace_db.close()
db.close()

print(f"\n{'='*72}")
print(f"  Total reasoning traces stored: {total}")
print(f"  DB location: {DB_PATH}")
print(f"{'='*72}\n")
