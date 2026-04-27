"""Event output schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    event_type: str
    risk_level: int = Field(ge=1, le=10)
    title: str
    occurred_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    description: str = ""
    source_text: str = ""
