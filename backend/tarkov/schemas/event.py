"""Event DTO used between extraction and persistence layers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    event_type: str
    risk_level: int = Field(ge=1, le=10)
    title: str
    occurred_at: datetime | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = ""
    source_text: str = ""
