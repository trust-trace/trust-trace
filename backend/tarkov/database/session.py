"""Database session management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all ORM models."""


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)


def init_engine(database_url: str):
    global engine
    if database_url.startswith("sqlite") and ":memory:" in database_url:
        engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(database_url, future=True)
    SessionLocal.configure(bind=engine)
    return engine


def create_all() -> None:
    if engine is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
