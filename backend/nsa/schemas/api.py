from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from reasoning.schemas import NSAReasoningTrace


class ScoreCompanyRequest(BaseModel):
    firm_id: int = Field(gt=0)
    correlation_id: str


class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float = Field(ge=0.0, le=1.0)
    people_scored: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    reasoning_traces: Optional[list[NSAReasoningTrace]] = None  # NEW: Optional reasoning traces for people scored
