# TrustWeb

Module C of AML Scoring Pipeline. Graph-based correlation engine that scores money-laundering risk by analyzing network connections.

## What it does

1. **Graph Construction** - Reads entities from PostgreSQL, creates nodes in Neo4j
2. **Edge Discovery** - Uses LLM to analyze evidence and discover connections between entities
3. **Risk Propagation** - Runs iterative algorithm to propagate risk through the network
4. **Score Calculation** - Produces trust score (0.0-1.0) with human-readable explanation

## Key principle

Tarkov writes standalone nodes only. TrustWeb creates all edges and calculates scores.

## Key components

- `graph/builder.py` - Phase 1: Creates nodes and discovers edges
- `graph/traversal.py` - Extracts subgraph from Neo4j
- `scoring/propagation.py` - Risk propagation algorithm
- `scoring/aggregator.py` - Final score computation
- `llm/` - OpenRouter client for edge discovery

## Usage

```python
from trust_web import score_firm

result = await score_firm(firm_id=123, pg_session=session)
# result.score, result.explanation, result.node_count, result.edge_count
```