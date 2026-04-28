"""Tests for the risk propagation algorithm."""

import pytest

from trust_web.config import TrustWebConfig
from trust_web.schemas import SubgraphData, SubgraphEdge, SubgraphNode
from trust_web.scoring.propagation import propagate_risk


def _config(**overrides) -> TrustWebConfig:
    defaults = dict(
        decay_factor=0.6,
        propagation_iterations=10,
        convergence_threshold=0.001,
    )
    defaults.update(overrides)
    return TrustWebConfig(**defaults)


class TestPropagateRisk:
    def test_empty_subgraph(self):
        sg = SubgraphData(root_firm_id=1)
        result = propagate_risk(sg, _config())
        assert result.converged is True
        assert result.risk_map == {}

    def test_isolated_node_keeps_own_risk(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[SubgraphNode(node_id="1", node_type="Company", name="Acme", depth=0, risk_level=0.8)],
            edges=[],
        )
        result = propagate_risk(sg, _config())
        assert result.risk_map["1"] == pytest.approx(0.8, abs=0.01)

    def test_risk_propagates_from_neighbor(self):
        """High-risk neighbor should increase the root's risk."""
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky", depth=1, risk_level=0.9),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=1.0),
            ],
        )
        result = propagate_risk(sg, _config())
        assert result.risk_map["1"] > 0.0

    def test_decay_reduces_distant_risk(self):
        """A risky node at depth 2 should contribute less than one at depth 1."""
        sg_close = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky", depth=1, risk_level=0.9),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=1.0)],
        )
        sg_far = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky", depth=2, risk_level=0.9),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=1.0)],
        )
        r_close = propagate_risk(sg_close, _config())
        r_far = propagate_risk(sg_far, _config())
        assert r_close.risk_map["1"] > r_far.risk_map["1"]

    def test_low_intensity_reduces_propagation(self):
        """Weak connection (low intensity) should propagate less risk."""
        sg_strong = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky", depth=1, risk_level=0.9),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=1.0)],
        )
        sg_weak = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.0),
                SubgraphNode(node_id="2", node_type="Company", name="Risky", depth=1, risk_level=0.9),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=0.1)],
        )
        r_strong = propagate_risk(sg_strong, _config())
        r_weak = propagate_risk(sg_weak, _config())
        assert r_strong.risk_map["1"] > r_weak.risk_map["1"]

    def test_convergence(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="A", depth=0, risk_level=0.5),
                SubgraphNode(node_id="2", node_type="Company", name="B", depth=1, risk_level=0.5),
            ],
            edges=[SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=0.8)],
        )
        result = propagate_risk(sg, _config(propagation_iterations=50))
        assert result.converged is True
        assert result.iterations_run < 50

    def test_scores_clamped_to_unit(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0, risk_level=0.95),
                SubgraphNode(node_id="2", node_type="Company", name="B", depth=1, risk_level=0.99),
                SubgraphNode(node_id="3", node_type="Company", name="C", depth=1, risk_level=0.99),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=1.0),
                SubgraphEdge(source_id="1", target_id="3", relationship_type="CONNECTION", intensity=1.0),
            ],
        )
        result = propagate_risk(sg, _config())
        for v in result.risk_map.values():
            assert 0.0 <= v <= 1.0

    def test_cycle_handling(self):
        """Cycles should not cause infinite growth."""
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="A", depth=0, risk_level=0.3),
                SubgraphNode(node_id="2", node_type="Company", name="B", depth=1, risk_level=0.3),
                SubgraphNode(node_id="3", node_type="Company", name="C", depth=1, risk_level=0.3),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION", intensity=0.8),
                SubgraphEdge(source_id="2", target_id="3", relationship_type="CONNECTION", intensity=0.8),
                SubgraphEdge(source_id="3", target_id="1", relationship_type="CONNECTION", intensity=0.8),
            ],
        )
        result = propagate_risk(sg, _config())
        for v in result.risk_map.values():
            assert 0.0 <= v <= 1.0
