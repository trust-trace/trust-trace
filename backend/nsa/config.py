from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NSAConfig:
    database_url: str
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls) -> "NSAConfig":
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
            api_host=os.getenv("NSA_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("NSA_API_PORT", "8083")),
        )
