"""SQLAlchemy ORM models for reasoning traces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from reasoning.session import Base


class ReasoningTraceModel(Base):
    """Model for storing domain-specific reasoning traces."""

    __tablename__ = "reasoning_traces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    classifier_name: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trace_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_reasoning_traces_classifier_created", "classifier_name", "created_at"),
        Index("ix_reasoning_traces_correlation_id", "correlation_id"),
        Index("ix_reasoning_traces_entity_id", "entity_id"),
    )
