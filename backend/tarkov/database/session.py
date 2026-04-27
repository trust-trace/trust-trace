"""Database engine/session lifecycle for Tarkov.

This module now supports both Postgres (SQLAlchemy) and Neo4j (neo4j-driver).
SQLAlchemy remains the canonical storage; Neo4j is optional graph layer for connections.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

# neo4j imports are imported lazily to avoid hard dependency if not used in tests
from neo4j import GraphDatabase, BoltDriver, Session as Neo4jNativeSession


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, future=True)

# Neo4j driver
_neo4j_driver: BoltDriver | None = None


def init_engine(database_url: str) -> Engine:
    """Initialize SQLAlchemy engine (Postgres/SQLite)."""
    global _engine
    if database_url.startswith("sqlite") and ":memory:" in database_url:
        _engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        _engine = create_engine(database_url, future=True)

    SessionLocal.configure(bind=_engine)
    return _engine


def init_neo4j(uri: str, user: str, password: str) -> BoltDriver:
    """Initialize Neo4j driver. Returns the driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
    return _neo4j_driver


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine().")
    return _engine


def get_neo4j_driver() -> BoltDriver:
    if _neo4j_driver is None:
        raise RuntimeError("Neo4j driver not initialized. Call init_neo4j().")
    return _neo4j_driver


def create_all() -> None:
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# A minimal Neo4j session wrapper to provide small compatibility with existing code
class Neo4jSession:
    def __init__(self, native_session: Neo4jNativeSession):
        self._session = native_session

    # ── context manager support ──────────────────────────────────────────
    def __enter__(self) -> "Neo4jSession":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # do not suppress exceptions

    # ── query helpers ─────────────────────────────────────────────────────
    def run(self, cypher: str, **params: Any):
        return self._session.run(cypher, **params)

    def close(self) -> None:
        self._session.close()

    def begin_transaction(self):
        return self._session.begin_transaction()

    def node_exists(self, label: str, key: str, value: Any) -> bool:
        q = f"MATCH (n:{label} {{{key}: $value}}) RETURN count(n) as c"
        rec = self.run(q, value=value).single()
        return rec["c"] > 0

    def create_node(self, label: str, props: dict) -> None:
        q = f"CREATE (n:{label} {{ {', '.join([f'`{k}`: $props.{k}' for k in props.keys()])} }})"
        self.run(q, props=props)


def get_neo4j_session() -> Neo4jSession:
    driver = get_neo4j_driver()
    native = driver.session()
    return Neo4jSession(native)
