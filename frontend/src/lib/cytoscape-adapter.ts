import type { Core, ElementDefinition, NodeDefinition, EdgeDefinition } from 'cytoscape';
import type { Neo4jGraphPayload, Neo4jGraphNode, Neo4jGraphEdge, Neo4jNodeKind } from './neo4j-graph';

/**
 * Normalized graph model that is renderer-agnostic
 */
export interface NormalizedGraphModel {
  nodes: NormalizedNode[];
  edges: NormalizedEdge[];
}

export interface NormalizedNode {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
  visual: {
    size: number;
    colorKey: string;
  };
}

export interface NormalizedEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

/**
 * Convert Neo4j payload to normalized graph model
 */
export function normalizeNeo4jGraph(payload: Neo4jGraphPayload): NormalizedGraphModel {
  const nodes: NormalizedNode[] = payload.nodes.map((node) => ({
    id: node.id,
    labels: [node.kind],
    properties: node.properties,
    visual: {
      size: getNodeSize(node.kind),
      colorKey: node.kind,
    },
  }));

  const edges: NormalizedEdge[] = payload.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.type,
    properties: edge.properties,
  }));

  return { nodes, edges };
}

/**
 * Color mapping for different node types
 */
const NODE_COLOR_MAP: Record<Neo4jNodeKind, string> = {
  company: '#1f77b4',
  person: '#ff7f0e',
  event: '#2ca02c',
};

/**
 * Size mapping for different node types
 */
const NODE_SIZE_MAP: Record<Neo4jNodeKind, number> = {
  company: 30,
  person: 22,
  event: 18,
};

export function getNodeColor(kind: string): string {
  return NODE_COLOR_MAP[kind as Neo4jNodeKind] || '#999999';
}

export function getNodeSize(kind: string): number {
  return NODE_SIZE_MAP[kind as Neo4jNodeKind] || 20;
}

/**
 * Convert normalized graph to Cytoscape elements
 */
export function toCytoscapeElements(model: NormalizedGraphModel): ElementDefinition[] {
  const nodeElements: NodeDefinition[] = model.nodes.map((node) => ({
    group: 'nodes',
    data: {
      id: node.id,
      label: node.properties.name ?? node.properties.label ?? node.id,
      labels: node.labels,
      kind: node.labels[0],
      raw: node,
    },
  }));

  const edgeElements: EdgeDefinition[] = model.edges.map((edge) => ({
    group: 'edges',
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.type,
      type: edge.type,
      raw: edge,
    },
  }));

  return [...nodeElements, ...edgeElements];
}
