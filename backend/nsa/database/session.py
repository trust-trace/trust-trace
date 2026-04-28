from __future__ import annotations

import os
from importlib import import_module

from tarkov.database.session import Base, SessionLocal, get_db, get_engine as _get_engine, init_engine as _init_engine

_current_database_url: str | None = None


def init_engine(database_url: str | None = None):
    global _current_database_url
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    _current_database_url = database_url
    return _init_engine(database_url)


def get_engine():
    return _get_engine()


def get_database_url() -> str | None:
    return _current_database_url


def close_engine() -> None:
    try:
        engine = get_engine()
    except RuntimeError:
        return
    engine.dispose()


def create_all() -> None:
    import_module("tarkov.database.models")
    import_module("nsa.database.models")
    Base.metadata.create_all(bind=get_engine())
