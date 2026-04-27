"""Runtime configuration for Tarkov."""

from __future__ import annotations

import os
from dataclasses import dataclass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Config:
    database_url: str
    log_level: str

    llm_provider: str
    llm_api_key: str
    llm_model: str

    article_input_source: str
    article_input_path: str
    company_reference_path: str
    keywords_file_path: str
    dead_letter_path: str

    api_host: str
    api_port: int

    enable_stage3_dispatch: bool
    event_classifier_url: str
    nsa_url: str
    trustweb_url: str

    enable_ingest_contract_headers: bool = False
    enforce_payload_version_header: bool = False
    expected_payload_version: str = "1"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            llm_provider=os.getenv("LLM_PROVIDER", "none"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            article_input_source=os.getenv("ARTICLE_INPUT_SOURCE", "jsonl"),
            article_input_path=os.getenv("ARTICLE_INPUT_PATH", "articles.jsonl"),
            company_reference_path=os.getenv("COMPANY_REFERENCE_PATH", "backend/tarkov/data/companies.json"),
            keywords_file_path=os.getenv("KEYWORDS_FILE_PATH", "backend/tarkov/data/aml_keywords.json"),
            dead_letter_path=os.getenv("DEAD_LETTER_PATH", "backend/tarkov/dead_letters.jsonl"),
            api_host=os.getenv("TARKOV_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("TARKOV_API_PORT", "8081")),
            enable_stage3_dispatch=env_bool("ENABLE_STAGE3_DISPATCH", False),
            event_classifier_url=os.getenv("EVENT_CLASSIFIER_URL", ""),
            nsa_url=os.getenv("NSA_URL", ""),
            trustweb_url=os.getenv("TRUSTWEB_URL", ""),
            enable_ingest_contract_headers=env_bool("ENABLE_INGEST_CONTRACT_HEADERS", False),
            enforce_payload_version_header=env_bool("ENFORCE_PAYLOAD_VERSION_HEADER", False),
            expected_payload_version=os.getenv("EXPECTED_PAYLOAD_VERSION", "1"),
        )
