"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tarkov.database.session import Base, SessionLocal, init_engine


@pytest.fixture()
def db_session() -> Session:
    engine = init_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_test_session() -> Session:
    engine = init_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return SessionLocal()
