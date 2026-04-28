"""Tests for FirmEnricher."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tarkov.database.session import Base
from tarkov.database.models import Event, Firm

from pipeline.firm_enricher import FirmEnricher


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


class TestFirmEnricher:
    def test_infer_founded_at_from_events(self, session):
        firm = Firm(full_name="TestCo", country="PL")
        session.add(firm)
        session.flush()

        earliest = datetime(2018, 6, 15)
        session.add(Event(
            firm_id=firm.id, title="Early", event_type="test",
            event_category="classical", risk_level=3, occurred_at=earliest,
        ))
        session.add(Event(
            firm_id=firm.id, title="Later", event_type="test",
            event_category="classical", risk_level=3,
            occurred_at=datetime(2023, 1, 1),
        ))
        session.flush()

        enricher = FirmEnricher(session)
        enricher.enrich(firm.id)
        session.flush()

        refreshed = session.get(Firm, firm.id)
        assert refreshed.founded_at == earliest

    def test_skips_if_founded_at_already_set(self, session):
        existing_date = datetime(2010, 1, 1)
        firm = Firm(full_name="TestCo", country="PL", founded_at=existing_date)
        session.add(firm)
        session.flush()

        session.add(Event(
            firm_id=firm.id, title="Event", event_type="test",
            event_category="classical", risk_level=3,
            occurred_at=datetime(2020, 1, 1),
        ))
        session.flush()

        enricher = FirmEnricher(session)
        enricher.enrich(firm.id)
        session.flush()

        refreshed = session.get(Firm, firm.id)
        assert refreshed.founded_at == existing_date

    def test_no_events_leaves_founded_at_none(self, session):
        firm = Firm(full_name="Empty Corp", country="PL")
        session.add(firm)
        session.flush()

        enricher = FirmEnricher(session)
        enricher.enrich(firm.id)
        session.flush()

        refreshed = session.get(Firm, firm.id)
        assert refreshed.founded_at is None

    def test_enrich_all(self, session):
        f1 = Firm(full_name="A", country="PL")
        f2 = Firm(full_name="B", country="PL")
        session.add_all([f1, f2])
        session.flush()

        session.add(Event(
            firm_id=f1.id, title="E1", event_type="test",
            event_category="classical", risk_level=3,
            occurred_at=datetime(2019, 1, 1),
        ))
        session.add(Event(
            firm_id=f2.id, title="E2", event_type="test",
            event_category="classical", risk_level=3,
            occurred_at=datetime(2021, 3, 1),
        ))
        session.flush()

        enricher = FirmEnricher(session)
        enricher.enrich_all([f1.id, f2.id])
        session.flush()

        assert session.get(Firm, f1.id).founded_at == datetime(2019, 1, 1)
        assert session.get(Firm, f2.id).founded_at == datetime(2021, 3, 1)

    def test_nonexistent_firm(self, session):
        enricher = FirmEnricher(session)
        enricher.enrich(99999)  # should not raise
