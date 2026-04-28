"""SQLAlchemy models and session management for reasoning traces."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all reasoning trace models."""

    pass


_engine: Engine | None = None
_engine_url: str | None = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)


def init_engine(database_url: str) -> Engine:
    """Initialize the database engine for reasoning traces."""
    global _engine, _engine_url
    if _engine is not None and _engine_url == database_url:
        return _engine
    if _engine is not None:
        _engine.dispose()
    if "sqlite" in database_url and ":memory:" in database_url:
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        _engine = create_engine(database_url)
    SessionLocal.configure(bind=_engine)
    _engine_url = database_url
    return _engine


def get_engine() -> Engine:
    """Get the current database engine."""
    if _engine is None:
        raise RuntimeError("Call init_engine() before using the database.")
    return _engine


def create_all() -> None:
    """Create all reasoning trace tables."""
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
