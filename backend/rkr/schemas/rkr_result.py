from pydantic import BaseModel, Field


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


class EnrichedArticle(BaseModel):
    source: dict
    article: dict
    metadata: dict
    rkr: RkrResult
