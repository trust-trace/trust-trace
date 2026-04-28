"""Runtime configuration for TrustWeb module."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


_DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_DATACLASS_KWARGS)
class TrustWebConfig:
    # Neo4j (reuses existing Tarkov driver when available)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "trusttrace"

    # OpenRouter LLM for intensity scoring
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"
    llm_explanation_model: str = "openai/gpt-4o"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://github.com/trust-trace/trust-trace"
    openrouter_x_title: str = "trust-trace"

    # Graph traversal
    max_depth: int = 5
    decay_factor: float = 0.6

    # Risk propagation
    propagation_iterations: int = 10
    convergence_threshold: float = 0.001

    # Batching
    intensity_batch_size: int = 10

    @classmethod
    def from_env(cls) -> TrustWebConfig:
        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "trusttrace"),
            llm_api_key=os.getenv("TRUSTWEB_LLM_API_KEY", os.getenv("LLM_API_KEY", "")),
            llm_model=os.getenv("TRUSTWEB_LLM_MODEL", "openai/gpt-4o-mini"),
            llm_explanation_model=os.getenv(
                "TRUSTWEB_LLM_EXPLANATION_MODEL", "openai/gpt-4o"
            ),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            openrouter_http_referer=os.getenv(
                "OPENROUTER_HTTP_REFERER", "https://github.com/trust-trace/trust-trace"
            ),
            openrouter_x_title=os.getenv("OPENROUTER_X_TITLE", "trust-trace"),
            max_depth=int(os.getenv("TRUSTWEB_MAX_DEPTH", "5")),
            decay_factor=float(os.getenv("TRUSTWEB_DECAY_FACTOR", "0.6")),
            propagation_iterations=int(
                os.getenv("TRUSTWEB_PROPAGATION_ITERATIONS", "10")
            ),
            convergence_threshold=float(
                os.getenv("TRUSTWEB_CONVERGENCE_THRESHOLD", "0.001")
            ),
            intensity_batch_size=int(os.getenv("TRUSTWEB_INTENSITY_BATCH_SIZE", "10")),
        )
