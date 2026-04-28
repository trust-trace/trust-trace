from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class PersonEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_kind: str
    source_url: HttpUrl
    title: str | None = None
    excerpt: str | None = None
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    claim_type: str

    @field_validator("source_kind", "claim_type")
    @classmethod
    def _required_text_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("title", "excerpt")
    @classmethod
    def _optional_text_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


class PersonScoreInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    person_id: int
    person_name: str
    role: str | None = None
    evidence: tuple[PersonEvidence, ...]
