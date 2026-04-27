"""Stage 1 payload schemas accepted by Tarkov."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    name: str = ""
    domain: str = ""
    url: str
    credibility_score: float = 0.5
    credibility_label: str = "unknown"

    model_config = {"extra": "ignore"}


class ArticleBody(BaseModel):
    title: str
    text: str
    published_at: datetime | None = None
    scraped_at: datetime | None = None
    canonical_url: str | None = None
    word_count: int | None = None
    authors: list[str] = Field(default_factory=list)
    language: str = "en"

    model_config = {"extra": "ignore"}


class ArticleMetadata(BaseModel):
    section: str | None = None
    tags: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    region: str | None = None
    discovery_method: str | None = None
    http_status: int | None = None

    model_config = {"extra": "ignore"}


class ArticleIn(BaseModel):
    source: SourceInfo
    article: ArticleBody
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)

    model_config = {"extra": "ignore"}
