"""Tests for the aggregator (final score computation)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trust_web.config import TrustWebConfig
from trust_web.schemas import SubgraphData, SubgraphEdge, SubgraphNode
from trust_web.scoring.aggregator import compute_trustweb_score, _build_summary, _format_top_contributors
from trust_web.schemas import PropagationResult


def _config() -> TrustWebConfig:
    return TrustWebConfig(llm_api_key="test-key")


def _mock_session():
    session = MagicMock()
    firm = MagicMock()
    firm.full_name = "Test Corp"
    session.get.return_value = firm
    return session


class TestBuildSummary:
    def test_counts_node_types(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="A", depth=0),
                SubgraphNode(node_id="2", node_type="Company", name="B", depth=1),
                SubgraphNode(node_id="3", node_type="Person", name="C", depth=1),
                SubgraphNode(node_id="4", node_type="Event", name="D", depth=2),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION"),
                SubgraphEdge(source_id="1", target_id="3", relationship_type="AFFILIATED_WITH"),
            ],
            max_depth_reached=2,
        )
        summary = _build_summary(sg)
        assert summary.total_nodes == 4
        assert summary.total_edges == 2
        assert summary.company_count == 2
        assert summary.person_count == 1
        assert summary.event_count == 1
        assert summary.max_depth == 2


class TestFormatTopContributors:
    def test_empty_risk_map(self):
        sg = SubgraphData(root_firm_id=1, nodes=[], edges=[])
        pr = PropagationResult(risk_map={})
        text = _format_top_contributors(sg, pr)
        assert "No significant" in text

    def test_formats_top_nodes(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky Co", depth=1),
            ],
        )
        pr = PropagationResult(risk_map={"1": 0.3, "2": 0.9})
        text = _format_top_contributors(sg, pr, limit=5)
        assert "Risky Co" in text
        assert "0.900" in text


class TestComputeTrustwebScore:
    @pytest.mark.asyncio
    async def test_isolated_firm_returns_zero(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[SubgraphNode(node_id="1", node_type="Company", name="Alone", depth=0)],
        )
        result = await compute_trustweb_score(1, sg, _mock_session(), _config())
        assert result.score == 0.0
        assert "No network connections" in result.explanation

    @pytest.mark.asyncio
    async def test_returns_result_with_score(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.2),
                SubgraphNode(node_id="2", node_type="Company", name="Neighbor", depth=1, risk_level=0.8),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=0.9)],
            max_depth_reached=1,
        )

        with patch("trust_web.scoring.aggregator.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "This company has moderate risk due to its network."
            result = await compute_trustweb_score(1, sg, _mock_session(), _config())

        assert 0.0 <= result.score <= 1.0
        assert result.firm_id == 1
        assert result.explanation != ""

    @pytest.mark.asyncio
    async def test_fallback_explanation_when_llm_fails(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Neighbor", depth=1, risk_level=0.5),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=0.5)],
            max_depth_reached=1,
        )

        with patch("trust_web.scoring.aggregator.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ""
            result = await compute_trustweb_score(1, sg, _mock_session(), _config())

        assert "TrustWeb analysis" in result.explanation
        assert "Test Corp" in result.explanation
