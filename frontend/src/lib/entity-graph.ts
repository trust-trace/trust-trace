import type {
  GraphEdge,
  GraphEntityType,
  GraphNode,
  GraphResponse,
  Risk,
} from '@/lib/data';

const ENTITY_TYPE_RANK: Record<GraphEntityType, number> = {
  Company: 0,
  Person: 1,
  Event: 2,
};

export type EntityGraphNode = GraphNode & {
  radius: number;
  orbit: number;
  emphasis: number;
  badge: string | null;
  summary: string;
  secondaryLabel: string | null;
  tintRisk: Risk;
};

export interface EntityGraphEdge extends GraphEdge {
  stroke: string;
  dashArray: string;
  width: number;
  summary: string;
}

export interface EntityGraphModel {
  rootId: string;
  nodes: EntityGraphNode[];
  edges: EntityGraphEdge[];
}

function getEventRisk(riskLevel?: number): Risk {
  if ((riskLevel ?? 0) >= 7) return 'high';
  if ((riskLevel ?? 0) >= 4) return 'medium';
  return 'low';
}

function nodeRadius(node: GraphNode): number {
  if (node.entityType === 'Company') {
    return node.depth === 0 ? 38 : node.depth === 1 ? 28 : 22;
  }

  if (node.entityType === 'Person') {
    return node.depth <= 1 ? 24 : 20;
  }

  return node.depth <= 1 ? 26 : 22;
}

function nodeOrbit(node: GraphNode): number {
  if (node.depth === 0) return 0;

  const base = node.depth === 1 ? 170 : 300;
  const bias = node.entityType === 'Company' ? -16 : node.entityType === 'Person' ? 8 : 32;
  return base + bias;
}

function nodeTintRisk(node: GraphNode): Risk {
  if (node.entityType === 'Company') {
    return node.data.risk ?? 'low';
  }

   if (node.entityType === 'Person') {
    return node.data.risk ?? 'low';
  }

  if (node.entityType === 'Event') {
    return node.data.risk ?? getEventRisk(node.data.riskLevel);
  }

  return 'low';
}

function nodeSummary(node: GraphNode): string {
  if (node.entityType === 'Company') {
    const sector = node.data.sector ?? 'Nieznany sektor';
    const score = node.data.score ?? 'n/a';
    return `${sector} · Trust ${score}`;
  }

  if (node.entityType === 'Person') {
    const role = node.data.role ?? 'Nieznana rola';
    const trust = node.data.trustScore ?? 'n/a';
    return `${role} · Trust ${trust}`;
  }

  const category = node.data.eventCategory ?? 'Zdarzenie';
  const risk = node.data.riskLevel ?? 'n/a';
  return `${category} · Ryzyko ${risk}`;
}

function nodeBadge(node: GraphNode): string | null {
  if (node.entityType === 'Company') {
    return typeof node.data.score === 'number' ? String(node.data.score) : null;
  }

  if (node.entityType === 'Person') {
    return typeof node.data.trustScore === 'number' ? String(node.data.trustScore) : null;
  }

  return typeof node.data.riskLevel === 'number' ? `R${node.data.riskLevel}` : null;
}

function nodeSecondaryLabel(node: GraphNode): string | null {
  if (node.entityType === 'Company') {
    return node.depth === 0 ? `Trust ${node.data.score ?? 'n/a'}` : null;
  }

  if (node.entityType === 'Person') {
    return node.data.role ? `${node.data.role}` : null;
  }

  return node.data.eventType ?? node.data.eventCategory ?? null;
}

function edgePresentation(edge: GraphEdge): Pick<EntityGraphEdge, 'stroke' | 'dashArray' | 'width' | 'summary'> {
  const intensity = Math.max(0.25, Math.min(edge.intensity ?? 0.55, 1));

  if (edge.relationshipType === 'AFFILIATED_WITH') {
    return {
      stroke: 'oklch(0.72 0.11 86)',
      dashArray: '',
      width: 1.8,
      summary: edge.connectionType || edge.label || 'Powiązanie afiliacyjne',
    };
  }

  if (edge.relationshipType === 'INVOLVED_IN') {
    return {
      stroke: 'oklch(0.62 0.13 235)',
      dashArray: '5 4',
      width: 1.7,
      summary: edge.connectionType || edge.label || 'Udział w zdarzeniu',
    };
  }

  if (edge.relationshipType === 'ABOUT') {
    return {
      stroke: 'oklch(0.66 0.12 18)',
      dashArray: '2 4',
      width: 1.6,
      summary: edge.sourceTitle || edge.label || 'Publikacja o zdarzeniu',
    };
  }

  return {
    stroke: 'oklch(0.58 0.16 272)',
    dashArray: '',
    width: 1.6 + intensity * 2.2,
    summary: edge.connectionType || edge.label || 'Połączenie sieciowe',
  };
}

function normalizeNode(node: GraphNode): EntityGraphNode {
  return {
    ...node,
    radius: nodeRadius(node),
    orbit: nodeOrbit(node),
    emphasis: 1 / (node.depth + 1),
    badge: nodeBadge(node),
    summary: nodeSummary(node),
    secondaryLabel: nodeSecondaryLabel(node),
    tintRisk: nodeTintRisk(node),
  };
}

function compareNodes(left: GraphNode, right: GraphNode): number {
  if (left.depth !== right.depth) return left.depth - right.depth;

  const typeDiff = ENTITY_TYPE_RANK[left.entityType] - ENTITY_TYPE_RANK[right.entityType];
  if (typeDiff !== 0) return typeDiff;

  const labelDiff = left.label.localeCompare(right.label);
  if (labelDiff !== 0) return labelDiff;

  return left.id.localeCompare(right.id);
}

function compareEdges(left: GraphEdge, right: GraphEdge): number {
  const leftKey = `${left.source}:${left.target}:${left.relationshipType}:${left.id}`;
  const rightKey = `${right.source}:${right.target}:${right.relationshipType}:${right.id}`;
  return leftKey.localeCompare(rightKey);
}

export function normalizeEntityGraph(graph: GraphResponse): EntityGraphModel {
  const sortedNodes = [...graph.nodes].sort(compareNodes);
  const knownIds = new Set(sortedNodes.map((node) => node.id));
  const sortedEdges = [...graph.edges]
    .filter((edge) => knownIds.has(edge.source) && knownIds.has(edge.target))
    .sort(compareEdges);

  return {
    rootId: graph.rootId,
    nodes: sortedNodes.map(normalizeNode),
    edges: sortedEdges.map((edge) => ({
      ...edge,
      ...edgePresentation(edge),
    })),
  };
}
