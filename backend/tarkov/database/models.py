"""SQLAlchemy models for Stage 2 persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tarkov.database.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RkrScore(Base):
    __tablename__ = "rkr_scoring"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    passed_threshold: Mapped[bool] = mapped_column(Boolean, nullable=False)
    categories_hit: Mapped[str] = mapped_column(Text, nullable=False)
    matched_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Firm(Base):
    __tablename__ = "firm"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    nip: Mapped[Optional[str]] = mapped_column(String(13), unique=True)
    regon: Mapped[Optional[str]] = mapped_column(String(14), unique=True)
    krs: Mapped[Optional[str]] = mapped_column(String(10), unique=True)
    country: Mapped[str] = mapped_column(String(3), nullable=False, default="PL")
    market_ticker: Mapped[Optional[str]] = mapped_column(String(32))
    market_exchange: Mapped[Optional[str]] = mapped_column(String(32))
    founded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    aliases: Mapped[list["FirmAlias"]] = relationship(
        back_populates="firm", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="firm", cascade="all, delete-orphan"
    )
    people: Mapped[list["Person"]] = relationship(back_populates="firm")


class FirmAlias(Base):
    __tablename__ = "firm_alias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    firm_id: Mapped[int] = mapped_column(
        ForeignKey("firm.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_type: Mapped[str] = mapped_column(String(50), nullable=False, default="name")
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_primary: Mapped[bool] = mapped_column(default=False)

    firm: Mapped[Firm] = relationship(back_populates="aliases")


class Event(Base):
    __tablename__ = "event"

    unique_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    firm_id: Mapped[int] = mapped_column(
        ForeignKey("firm.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="classical"
    )
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float)
    source_text_quote: Mapped[Optional[str]] = mapped_column(Text)

    firm: Mapped[Firm] = relationship(back_populates="events")
    sources: Mapped[list["Source"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    people_links: Mapped[list["PersonEvent"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    connection_entities: Mapped[list["ConnectionEntity"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("event.unique_id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="original"
    )
    source_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="article"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    credibility: Mapped[Optional[float]] = mapped_column(Float)

    event: Mapped[Event] = relationship(back_populates="sources")


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    firm_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("firm.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    firm: Mapped[Optional[Firm]] = relationship(back_populates="people")
    event_links: Mapped[list["PersonEvent"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class PersonEvent(Base):
    __tablename__ = "person_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("event.unique_id", ondelete="CASCADE"), nullable=False
    )
    role_in_event: Mapped[Optional[str]] = mapped_column(String(100))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    person: Mapped[Person] = relationship(back_populates="event_links")
    event: Mapped[Event] = relationship(back_populates="people_links")


class ConnectionEntity(Base):
    __tablename__ = "connection_entity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    connection_event_id: Mapped[str] = mapped_column(
        ForeignKey("event.unique_id", ondelete="CASCADE"), nullable=False
    )
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_1_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_1_id: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_1_name: Mapped[Optional[str]] = mapped_column(Text)
    entity_2_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_2_id: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_2_name: Mapped[Optional[str]] = mapped_column(Text)
    relationship_description: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event: Mapped[Event] = relationship(back_populates="connection_entities")


class ArticleMetadata(Base):
    __tablename__ = "article_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    article_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    correlation_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    discovery_method: Mapped[Optional[str]] = mapped_column(String(50))
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    companies_found: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_job"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ingest_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    article_id: Mapped[Optional[str]] = mapped_column(String(50))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
