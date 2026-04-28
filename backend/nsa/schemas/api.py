from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreCompanyRequest(BaseModel):
    firm_id: int = Field(gt=0)
    correlation_id: str


class ScoreCompanyResponse(BaseModel):
    status: str
    firm_id: int
    company_risk_score: float = Field(ge=0.0, le=1.0)
    people_scored: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
