"""Tests for TrustWeb timeline filtering."""

from datetime import datetime

from trust_web.graph.traversal import filter_subgraph_by_cutoff
from trust_web.schemas import SubgraphData, SubgraphEdge, SubgraphNode


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day)


class TestFilterSubgraphByCutoff:
    def _make_subgraph(self) -> SubgraphData:
        return SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0),
                SubgraphNode(node_id="evt1", node_type="Event", name="Early Event", depth=1,
                             occurred_at=_dt(2020)),
                SubgraphNode(node_id="evt2", node_type="Event", name="Late Event", depth=1,
                             occurred_at=_dt(2025)),
                SubgraphNode(node_id="p1", node_type="Person", name="Person A", depth=1),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="evt1", relationship_type="ABOUT",
                             event_occurred_at=_dt(2020)),
                SubgraphEdge(source_id="1", target_id="evt2", relationship_type="ABOUT",
                             event_occurred_at=_dt(2025)),
                SubgraphEdge(source_id="p1", target_id="evt1", relationship_type="INVOLVED_IN",
                             event_occurred_at=_dt(2020)),
                SubgraphEdge(source_id="p1", target_id="evt2", relationship_type="INVOLVED_IN",
                             event_occurred_at=_dt(2025)),
            ],
            max_depth_reached=1,
        )

    def test_cutoff_before_all_events(self):
        sg = self._make_subgraph()
        filtered = filter_subgraph_by_cutoff(sg, _dt(2019))
        # Only the root company node should survive
        assert len(filtered.nodes) == 1
        assert filtered.nodes[0].node_type == "Company"
        assert len(filtered.edges) == 0

    def test_cutoff_between_events(self):
        sg = self._make_subgraph()
        filtered = filter_subgraph_by_cutoff(sg, _dt(2022))
        node_ids = {n.node_id for n in filtered.nodes}
        assert "1" in node_ids       # Company always survives
        assert "evt1" in node_ids    # Early event survives
        assert "evt2" not in node_ids  # Late event filtered out
        assert "p1" in node_ids      # Person survives via evt1 edge

    def test_cutoff_after_all_events(self):
        sg = self._make_subgraph()
        filtered = filter_subgraph_by_cutoff(sg, _dt(2026))
        assert len(filtered.nodes) == 4
        assert len(filtered.edges) == 4

    def test_edges_filtered_by_event_date(self):
        sg = self._make_subgraph()
        filtered = filter_subgraph_by_cutoff(sg, _dt(2022))
        for e in filtered.edges:
            assert e.event_occurred_at is None or e.event_occurred_at <= _dt(2022)

    def test_person_without_surviving_edges_is_removed(self):
        """Person connected only to future events should be filtered out."""
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0),
                SubgraphNode(node_id="evt1", node_type="Event", name="Future Event", depth=1,
                             occurred_at=_dt(2025)),
                SubgraphNode(node_id="p1", node_type="Person", name="Person B", depth=1),
            ],
            edges=[
                SubgraphEdge(source_id="p1", target_id="evt1", relationship_type="INVOLVED_IN",
                             event_occurred_at=_dt(2025)),
            ],
            max_depth_reached=1,
        )
        filtered = filter_subgraph_by_cutoff(sg, _dt(2022))
        node_ids = {n.node_id for n in filtered.nodes}
        assert "p1" not in node_ids

    def test_company_nodes_always_kept(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0),
                SubgraphNode(node_id="2", node_type="Company", name="Neighbor", depth=1),
            ],
            edges=[
                SubgraphEdge(source_id="1", target_id="2", relationship_type="CONNECTION",
                             intensity=0.5),
            ],
            max_depth_reached=1,
        )
        filtered = filter_subgraph_by_cutoff(sg, _dt(2019))
        assert len(filtered.nodes) == 2

    def test_events_with_no_date_are_kept(self):
        sg = SubgraphData(
            root_firm_id=1,
            nodes=[
                SubgraphNode(node_id="1", node_type="Company", name="Root", depth=0),
                SubgraphNode(node_id="evt1", node_type="Event", name="No-date Event", depth=1,
                             occurred_at=None),
            ],
            edges=[],
            max_depth_reached=1,
        )
        filtered = filter_subgraph_by_cutoff(sg, _dt(2019))
        node_ids = {n.node_id for n in filtered.nodes}
        assert "evt1" in node_ids
