from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from reasoning.schemas import NSAReasoningTrace


class ScoreCompanyRequest(BaseModel):
    firm_id: int = Field(gt=0)
    correlation_id: str
    include_reasoning: bool = False


class PersonScoreSummary(BaseModel):
    """Summary of scored person with optional trace reference."""
    person_id: int
    person_name: str
    risk_score: float = Field(ge=0.0, le=1.0)
    reasoning_trace: Optional[NSAReasoningTrace] = None


class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float = Field(ge=0.0, le=1.0)
    people_scored: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    people_summaries: Optional[list[PersonScoreSummary]] = None  # NEW: Per-person scores with optional trace IDs
