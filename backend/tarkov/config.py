"""Configuration management for Tarkov."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    database_url: str
    llm_provider: str
    llm_api_key: str
    llm_model: str
    log_level: str
    keywords_file_path: str
    article_input_source: str
    article_input_path: str
    company_reference_path: str
    dead_letter_path: str
    api_host: str
    api_port: int
    enable_stage3_dispatch: bool
    event_classifier_url: str
    nsa_url: str
    trustweb_url: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            keywords_file_path=os.getenv("KEYWORDS_FILE_PATH", "backend/tarkov/data/aml_keywords.json"),
            article_input_source=os.getenv("ARTICLE_INPUT_SOURCE", "jsonl"),
            article_input_path=os.getenv("ARTICLE_INPUT_PATH", "articles.jsonl"),
            company_reference_path=os.getenv(
                "COMPANY_REFERENCE_PATH",
                "backend/tarkov/data/companies.json",
            ),
            dead_letter_path=os.getenv("DEAD_LETTER_PATH", "backend/tarkov/dead_letters.jsonl"),
            api_host=os.getenv("TARKOV_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("TARKOV_API_PORT", "8081")),
            enable_stage3_dispatch=_as_bool(os.getenv("ENABLE_STAGE3_DISPATCH"), default=False),
            event_classifier_url=os.getenv("EVENT_CLASSIFIER_URL", ""),
            nsa_url=os.getenv("NSA_URL", ""),
            trustweb_url=os.getenv("TRUSTWEB_URL", ""),
        )
