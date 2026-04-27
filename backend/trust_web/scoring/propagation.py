"""Attenuated Risk Diffusion — iterative risk propagation on the subgraph."""

from __future__ import annotations

import logging
from collections import defaultdict

from trust_web.config import TrustWebConfig
from trust_web.schemas import PropagationResult, SubgraphData

logger = logging.getLogger(__name__)

# Blending weight: how much of the node's own risk vs. propagated risk to keep
_SELF_WEIGHT = 0.7
_PROPAGATED_WEIGHT = 0.3


def propagate_risk(
    subgraph: SubgraphData,
    config: TrustWebConfig,
) -> PropagationResult:
    """Run iterative risk diffusion and return the full risk map.

    Algorithm:
    1. Initialize risk[node] from node.risk_level (or 0).
    2. Build an adjacency structure from edges.
    3. Iterate: each node blends its own risk with a weighted average
       of neighbor risks, attenuated by edge intensity × decay^depth.
    4. Stop when converged or max iterations reached.
    """
    if not subgraph.nodes:
        return PropagationResult(converged=True)

    # Initialize risk map
    risk: dict[str, float] = {}
    depth_map: dict[str, int] = {}
    for node in subgraph.nodes:
        risk[node.node_id] = node.risk_level if node.risk_level is not None else 0.0
        depth_map[node.node_id] = node.depth

    # Build undirected adjacency: node_id → [(neighbor_id, intensity)]
    adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for edge in subgraph.edges:
        intensity = edge.intensity if edge.intensity is not None else 0.5
        adjacency[edge.source_id].append((edge.target_id, intensity))
        adjacency[edge.target_id].append((edge.source_id, intensity))

    # Iterative propagation
    converged = False
    iterations_run = 0

    for iteration in range(config.propagation_iterations):
        iterations_run = iteration + 1
        max_delta = 0.0
        new_risk: dict[str, float] = {}

        for node_id, current_risk in risk.items():
            neighbors = adjacency.get(node_id, [])
            if not neighbors:
                new_risk[node_id] = current_risk
                continue

            incoming_risk = 0.0
            total_weight = 0.0

            for neighbor_id, edge_intensity in neighbors:
                neighbor_depth = depth_map.get(neighbor_id, 1)
                hop_decay = config.decay_factor ** max(neighbor_depth, 1)
                weight = edge_intensity * hop_decay
                incoming_risk += risk.get(neighbor_id, 0.0) * weight
                total_weight += weight

            if total_weight > 0:
                # Cap the propagated signal at the strongest neighbor's risk
                # so the weighted mean doesn't erase intensity/decay effects
                propagated = incoming_risk / max(total_weight, 1.0)
                blended = _SELF_WEIGHT * current_risk + _PROPAGATED_WEIGHT * propagated
            else:
                blended = current_risk

            new_risk[node_id] = blended
            max_delta = max(max_delta, abs(blended - current_risk))

        risk = new_risk

        if max_delta < config.convergence_threshold:
            converged = True
            logger.debug("Propagation converged at iteration %d (delta=%.6f)", iterations_run, max_delta)
            break

    # Clamp all values to [0, 1]
    for nid in risk:
        risk[nid] = max(0.0, min(1.0, risk[nid]))

    return PropagationResult(
        risk_map=risk,
        iterations_run=iterations_run,
        converged=converged,
    )
