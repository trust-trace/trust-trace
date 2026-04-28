from __future__ import annotations

from datetime import datetime

import pytest

from nsa.database.session import Base, SessionLocal, create_all, init_engine
from tarkov.database.models import Event, Firm, Person, Source


@pytest.fixture()
def db_session():
    engine = init_engine("sqlite+pysqlite:///:memory:")
    create_all()
    session = SessionLocal()

    firm = Firm(full_name="Acme Sp. z o.o.", country="PL")
    session.add(firm)
    session.flush()

    person = Person(name="Jane Doe", role="Director", firm_id=firm.id)
    session.add(person)
    session.flush()

    event = Event(
        firm_id=firm.id,
        title="Investigation mention",
        event_type="news",
        event_category="classical",
        risk_level=3,
        occurred_at=datetime(2024, 1, 1),
    )
    session.add(event)
    session.flush()

    source = Source(event_id=event.unique_id, url="https://example.com/article")
    session.add(source)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
