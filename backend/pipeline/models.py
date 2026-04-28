"""SQLAlchemy models for the E2E pipeline orchestration tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from tarkov.database.session import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    phase: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    article_target: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    articles_scraped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    firm_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    final_scores: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FinalScoreTimeline(Base):
    __tablename__ = "final_score_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    firm_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bucket_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bucket_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    eem_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trustweb_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    nsa_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
