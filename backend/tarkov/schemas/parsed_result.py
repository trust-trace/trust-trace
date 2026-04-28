"""Parsed payload contracts emitted by Tarkov."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LLMSummary(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    key_topics: list[str] = Field(default_factory=list)


class SourceReference(BaseModel):
    url: str
    title: str
    source_text: str
    published_at: datetime | None = None
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str = "en"


class EventExtraction(BaseModel):
    event_type: str
    event_category: str = "classical"
    title: str
    description: str
    risk_level: int = Field(ge=1, le=10)
    occurred_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference
    reasoning_trace_id: Optional[int] = None  # NEW: ID to reasoning trace in database


class PersonExtraction(BaseModel):
    name: str
    role: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference


class ParsedResult(BaseModel):
    article_id: str
    processed_at: datetime
    llm_summary: LLMSummary
    events: list[EventExtraction] = Field(default_factory=list)
    people: list[PersonExtraction] = Field(default_factory=list)
    company_matches: list[str] = Field(default_factory=list)
    firm_ids: list[int] = Field(default_factory=list)
    language: str = "en"
    total_risk_score: float = 0.0


class ParsingEvent(BaseModel):
    event_type: str = "article.parsed"
    timestamp: datetime
    source_system: str = "tarkov"
    parsed_result: ParsedResult
    firm_ids: list[int] = Field(default_factory=list)
    correlation_id: str
    target_modules: list[str] = Field(default_factory=lambda: ["event_classifier", "nsa"])

    @model_validator(mode="after")
    def _sync_firm_ids(self):
        parsed_firm_ids = list(self.parsed_result.firm_ids)
        if not self.firm_ids:
            self.firm_ids = parsed_firm_ids
            return self
        if self.firm_ids != parsed_firm_ids:
            raise ValueError("firm_ids must match parsed_result.firm_ids")
        return self
