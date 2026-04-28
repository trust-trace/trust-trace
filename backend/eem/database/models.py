from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from eem.database.session import Base

# ForeignKey declarations are intentionally omitted: 'event' and 'firm' belong to
# Tarkov's Base, not EEM's. create_all() only sees EEM's Base and would fail trying
# to resolve those references. DB-level constraints are managed by migrations.


class EventEnrichment(Base):
    __tablename__ = "event_enrichment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    impact: Mapped[float] = mapped_column(Float, nullable=False)
    source_tier: Mapped[str] = mapped_column(String(10), nullable=False)
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    entities: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    model_used: Mapped[str] = mapped_column(String(80), nullable=False)
    enriched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FirmScore(Base):
    __tablename__ = "firm_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    firm_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk: Mapped[str] = mapped_column(String(10), nullable=False)
    trend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_history: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
