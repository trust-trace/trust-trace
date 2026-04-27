export type Neo4jNodeKind = 'company' | 'person' | 'event';

export interface Neo4jGraphNode {
  id: string;
  kind: Neo4jNodeKind;
  label: string;
  properties: Record<string, unknown>;
}

export interface Neo4jGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface Neo4jGraphPayload {
  nodes: Neo4jGraphNode[];
  edges: Neo4jGraphEdge[];
}

export function toEdgeKey(edge: Neo4jGraphEdge): string {
  return edge.id;
}

export function getConnectedNodeIds(
  nodeId: string | null,
  edges: Neo4jGraphEdge[]
): Set<string> {
  if (!nodeId) return new Set();

  const ids = new Set<string>([nodeId]);

  for (const edge of edges) {
    if (edge.source === nodeId) ids.add(edge.target);
    if (edge.target === nodeId) ids.add(edge.source);
  }

  return ids;
}
