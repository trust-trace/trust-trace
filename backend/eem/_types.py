from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from reasoning.schemas import EEMReasoningTrace


class FirmNotFoundError(Exception):
    pass


@dataclass
class _SourceRow:
    title: str | None
    url: str
    published_at: datetime | None
    content_excerpt: str


@dataclass
class _PersonRow:
    name: str
    role: str | None
    role_in_event: str | None


@dataclass
class _EventRow:
    event_id: str
    firm_id: int
    event_type: str
    title: str
    risk_level: int
    occurred_at: datetime
    source_text_quote: str | None
    sources: list[_SourceRow] = field(default_factory=list)
    people: list[_PersonRow] = field(default_factory=list)


@dataclass
class _EventFields:
    sentiment: float
    impact: float
    source_tier: str
    keywords: list[str]
    excerpt: str
    entities: list[str]
    reasoning_trace: Optional[EEMReasoningTrace] = None
