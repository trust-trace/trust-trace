"""Person DTO for extraction output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonOut(BaseModel):
    name: str
    role: str = "unknown"
    description: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    mentioned_in_context: str = ""
