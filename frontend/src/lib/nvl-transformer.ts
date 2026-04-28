import type { Neo4jGraphNode, Neo4jGraphEdge, Neo4jGraphPayload } from './neo4j-graph';

/**
 * NVL-compatible node structure with styling properties
 */
export interface NvlNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

/**
 * NVL-compatible relationship structure
 */
export interface NvlRelationship {
  id: string;
  type: string;
  from: string;
  to: string;
  properties: Record<string, unknown>;
}

/**
 * NVL graph data structure
 */
export interface NvlGraphData {
  nodes: NvlNode[];
  relationships: NvlRelationship[];
}

export interface NvlTransformResult {
  nodes: NvlNode[];
  relationships: NvlRelationship[];
  empty: boolean;
}

/**
 * Color mapping for different node types
 */
const NODE_COLOR_MAP: Record<string, string> = {
  company: 'oklch(0.22 0.03 255)',
  person: 'oklch(0.62 0.12 210)',
  event: 'oklch(0.72 0.1 30)',
};

/**
 * Size mapping for different node types
 */
const NODE_SIZE_MAP: Record<string, number> = {
  company: 28,
  person: 20,
  event: 16,
};

/**
 * Color mapping for different relationship types
 */
const RELATIONSHIP_COLOR_MAP: Record<string, string> = {
  ABOUT: 'oklch(0.65 0.08 35)',
  INVOLVED_IN: 'oklch(0.62 0.1 220)',
  AFFILIATED_WITH: 'oklch(0.6 0.12 145)',
};

/**
 * Default relationship color for unmapped types
 */
const DEFAULT_RELATIONSHIP_COLOR = 'oklch(0.58 0.08 300)';

/**
 * Get color for a node based on its kind
 */
export function getNodeColor(kind: string): string {
  return NODE_COLOR_MAP[kind] || NODE_COLOR_MAP.event;
}

/**
 * Get size for a node based on its kind
 */
export function getNodeSize(kind: string): number {
  return NODE_SIZE_MAP[kind] || NODE_SIZE_MAP.event;
}

/**
 * Get color for a relationship based on its type
 */
export function getRelationshipColor(type: string): string {
  return RELATIONSHIP_COLOR_MAP[type] || DEFAULT_RELATIONSHIP_COLOR;
}

/**
 * Transform a Neo4j graph payload into NVL format
 * Converts nodes array and edges array into nodes and relationships format
 * with proper styling attributes applied
 */
export function transformToNvlGraph(payload: Neo4jGraphPayload): NvlGraphData {
  const nodesInput = payload.nodes ?? [];
  const edgesInput = payload.edges ?? [];

  // Transform nodes
  const nodes: NvlNode[] = nodesInput.map((node: Neo4jGraphNode) => ({
    id: node.id,
    label: node.label,
    properties: node.properties,
  }));

  // Transform edges to relationships
  const relationships: NvlRelationship[] = edgesInput.map(
    (edge: Neo4jGraphEdge) => ({
      id: edge.id,
      type: edge.type,
      from: edge.source,
      to: edge.target,
      properties: edge.properties,
    })
  );

  return {
    nodes,
    relationships,
  };
}
