from typing import Optional

from pydantic import BaseModel, Field

from reasoning.schemas import RKRReasoningTrace


class RkrMatch(BaseModel):
    keyword: str
    category: str
    weight: float
    in_title: bool
    context: str
    occurrences: int


class RkrResult(BaseModel):
    matched_keywords: list[RkrMatch]
    categories_hit: list[str]
    risk_score: float = Field(ge=0.0, le=1.0)
    passed_threshold: bool
    reasoning_trace: Optional[RKRReasoningTrace] = None  # NEW: Optional reasoning trace


class EnrichedArticle(BaseModel):
    source: dict
    article: dict
    metadata: dict
    rkr: RkrResult
