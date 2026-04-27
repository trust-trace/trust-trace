"""Parsed result and event emission schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LLMSummary(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    key_topics: list[str] = Field(default_factory=list)


class SourceReference(BaseModel):
    url: str
    title: str
    source_text: str
    published_at: datetime | None = None
    credibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    language: str = "en"


class EventExtraction(BaseModel):
    event_type: str
    title: str
    description: str
    risk_level: int = Field(ge=1, le=10)
    occurred_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference


class PersonExtraction(BaseModel):
    name: str
    role: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference


class ConnectionExtraction(BaseModel):
    connection_type: str
    entity_1_type: str
    entity_1_id: str
    entity_1_name: str
    entity_2_type: str
    entity_2_id: str
    entity_2_name: str
    relationship_description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    source_reference: SourceReference


class ParsedResult(BaseModel):
    article_id: str
    processed_at: datetime
    llm_summary: LLMSummary
    events: list[EventExtraction] = Field(default_factory=list)
    people: list[PersonExtraction] = Field(default_factory=list)
    connections: list[ConnectionExtraction] = Field(default_factory=list)
    company_matches: list[str] = Field(default_factory=list)
    language: str = "en"
    total_risk_score: float = 0.0


class ParsingEvent(BaseModel):
    event_type: str = "article.parsed"
    timestamp: datetime
    source_system: str = "tarkov"
    parsed_result: ParsedResult
    correlation_id: str
    target_modules: list[str] = Field(default_factory=lambda: ["event_classifier", "nsa", "trustweb"])
