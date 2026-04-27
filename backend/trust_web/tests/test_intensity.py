"""Tests for intensity scoring."""

import pytest
from unittest.mock import AsyncMock, patch

from trust_web.config import TrustWebConfig
from trust_web.schemas import ConnectionForScoring, IntensityResult
from trust_web.scoring.intensity import score_connection, score_connections_batch, _fallback_result


def _config(**overrides) -> TrustWebConfig:
    return TrustWebConfig(llm_api_key="test-key", **overrides)


def _sample_connection(**overrides) -> ConnectionForScoring:
    defaults = dict(
        connection_type="shared_director",
        entity_1_name="Acme Corp",
        entity_1_type="company",
        entity_2_name="Beta Holdings",
        entity_2_type="company",
        relationship_description="Shared board member Jan Kowalski",
        source_text_quote="Jan Kowalski sits on boards of both Acme and Beta.",
    )
    defaults.update(overrides)
    return ConnectionForScoring(**defaults)


class TestFallbackResult:
    def test_uses_relationship_description_when_present(self):
        conn = _sample_connection(relationship_description="Some description")
        result = _fallback_result(conn)
        assert result.intensity == 0.5
        assert result.description == "Some description"

    def test_generates_template_when_no_description(self):
        conn = _sample_connection(relationship_description="")
        result = _fallback_result(conn)
        assert "Acme Corp" in result.description
        assert "Beta Holdings" in result.description
        assert "shared_director" in result.description


class TestScoreConnection:
    @pytest.mark.asyncio
    async def test_successful_llm_response(self):
        config = _config()
        conn = _sample_connection()

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intensity": 0.85, "description": "Strong board overlap."}'
            result = await score_connection(conn, config)

        assert result.intensity == pytest.approx(0.85)
        assert result.description == "Strong board overlap."

    @pytest.mark.asyncio
    async def test_fallback_on_empty_llm_response(self):
        config = _config()
        conn = _sample_connection()

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ""
            result = await score_connection(conn, config)

        assert result.intensity == 0.5

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_json(self):
        config = _config()
        conn = _sample_connection()

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "not json at all"
            result = await score_connection(conn, config)

        assert result.intensity == 0.5

    @pytest.mark.asyncio
    async def test_clamps_intensity(self):
        config = _config()
        conn = _sample_connection()

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intensity": 1.5, "description": "Very high."}'
            result = await score_connection(conn, config)

        assert result.intensity == 1.0


class TestScoreConnectionsBatch:
    @pytest.mark.asyncio
    async def test_batch_scoring(self):
        config = _config(intensity_batch_size=2)
        connections = [_sample_connection() for _ in range(3)]

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intensity": 0.7, "description": "Moderate connection."}'
            results = await score_connections_batch(connections, config)

        assert len(results) == 3
        assert all(r.intensity == pytest.approx(0.7) for r in results)

    @pytest.mark.asyncio
    async def test_handles_exceptions_in_batch(self):
        config = _config(intensity_batch_size=2)
        connections = [_sample_connection() for _ in range(2)]

        with patch("trust_web.scoring.intensity.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = [RuntimeError("boom"), '{"intensity": 0.6, "description": "ok"}']
            results = await score_connections_batch(connections, config)

        assert len(results) == 2
        assert results[0].intensity == 0.5  # fallback
