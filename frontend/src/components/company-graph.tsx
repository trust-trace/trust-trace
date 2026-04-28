'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { TraceDrawer } from './trace-drawer';
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type NodeProps,
} from '@xyflow/react';
import dagre from 'dagre';
import '@xyflow/react/dist/style.css';

import {
  normalizeEntityGraph,
  rerootEntityGraph,
  type EntityGraphEdge,
  type EntityGraphNode,
} from '@/lib/entity-graph';
import type { Company, GraphEntityType, GraphResponse, Risk } from '@/lib/data';
import { riskColor, riskLabel } from './sidebar';

interface CompanyGraphProps {
  company: Company;
  graph: GraphResponse;
  onSelectCompany: (id: string) => void;
}

/* ------------------------------------------------------------------ */
/* Visual encoding tables                                              */
/* ------------------------------------------------------------------ */

const BASE_NODE_WIDTH: Record<GraphEntityType, number> = {
  Company: 180,
  Person: 160,
  Event: 220,
};

/** Minimum height for one title line + chrome; must match real CSS in globals (.tt-rf-node). */
const BASE_NODE_HEIGHT: Record<GraphEntityType, number> = {
  Company: 72,
  Person: 74,
  Event: 88,
};

const MAX_NODE_WIDTH = 280;
const CHAR_WIDTH_ESTIMATE = 7;
const NODE_PADDING_X = 28;
/** Per wrapped title line; keep in sync with .tt-rf-node-title line-height × font-size. */
const LINE_HEIGHT = 17;

function estimateNodeSize(node: EntityGraphNode): { width: number; height: number } {
  const label =
    node.entityType === 'Event'
      ? truncate(node.label, 56)
      : node.entityType === 'Company'
        ? (node.data.short ?? node.label)
        : node.label;
  const baseW = BASE_NODE_WIDTH[node.entityType];
  const baseH = BASE_NODE_HEIGHT[node.entityType];

  const textWidth = label.length * CHAR_WIDTH_ESTIMATE + NODE_PADDING_X;
  const width = Math.min(MAX_NODE_WIDTH, Math.max(baseW, textWidth));

  const availableTextWidth = width - NODE_PADDING_X;
  const charsPerLine = Math.max(1, Math.floor(availableTextWidth / CHAR_WIDTH_ESTIMATE));
  const lines = Math.ceil(label.length / charsPerLine);
  const extraHeight = Math.max(0, lines - 1) * LINE_HEIGHT;
  const height = baseH + extraHeight;

  return { width, height };
}

const EDGE_STYLE: Record<
  EntityGraphEdge['relationshipType'],
  { stroke: string; strokeWidth: number; strokeDasharray?: string; label: string; description: string }
> = {
  CONNECTION: {
    stroke: 'oklch(0.55 0.16 272)',
    strokeWidth: 2.4,
    label: 'Connection',
    description: 'Company ↔ company business tie',
  },
  AFFILIATED_WITH: {
    stroke: 'oklch(0.58 0.13 248)',
    strokeWidth: 1.8,
    label: 'Affiliated',
    description: 'Person ↔ company affiliation',
  },
  INVOLVED_IN: {
    stroke: 'oklch(0.62 0.15 32)',
    strokeWidth: 1.8,
    strokeDasharray: '6 4',
    label: 'Involved',
    description: 'Person ↔ event involvement',
  },
  ABOUT: {
    stroke: 'oklch(0.55 0.05 250)',
    strokeWidth: 1.4,
    strokeDasharray: '2 4',
    label: 'About',
    description: 'Publication / mention link',
  },
};

function riskFromLevel(level: number | undefined): Risk {
  if ((level ?? 0) >= 7) return 'high';
  if ((level ?? 0) >= 4) return 'medium';
  return 'low';
}

function eventRiskColor(level: number | undefined, risk?: Risk): string {
  return riskColor(risk ?? riskFromLevel(level));
}

/* ------------------------------------------------------------------ */
/* Custom node components                                              */
/* ------------------------------------------------------------------ */

type CompanyNodeData = {
  node: Extract<EntityGraphNode, { entityType: 'Company' }>;
  isRoot: boolean;
  isSelected: boolean;
};
type PersonNodeData = {
  node: Extract<EntityGraphNode, { entityType: 'Person' }>;
  isSelected: boolean;
  risk: Risk;
};
type EventNodeData = {
  node: Extract<EntityGraphNode, { entityType: 'Event' }>;
  isSelected: boolean;
};

function CompanyNode({ data }: NodeProps<Node<CompanyNodeData>>) {
  const { node, isRoot, isSelected } = data;
  const accent = riskColor(node.data.risk ?? 'low');
  return (
    <div
      className={`tt-rf-node tt-rf-company${isRoot ? ' is-root' : ''}${isSelected ? ' is-selected' : ''}`}
      style={{ borderColor: accent }}
    >
      <Handle type="target" position={Position.Top} className="tt-rf-handle" />
      <div className="tt-rf-node-row">
        <span className="tt-rf-node-kind" style={{ background: accent }}>
          {isRoot ? 'ROOT' : 'COMPANY'}
        </span>
        <span className="tt-rf-node-score" style={{ color: accent }}>
          {node.data.score ?? '—'}
        </span>
      </div>
      <div className="tt-rf-node-title">{node.data.short ?? node.label}</div>
      <div className="tt-rf-node-sub">
        {node.data.sector ?? '—'} · {riskLabel(node.data.risk ?? 'low')}
      </div>
      <Handle type="source" position={Position.Bottom} className="tt-rf-handle" />
    </div>
  );
}

function PersonNode({ data }: NodeProps<Node<PersonNodeData>>) {
  const { node, isSelected, risk } = data;
  const accent = riskColor(risk);
  return (
    <div
      className={`tt-rf-node tt-rf-person${isSelected ? ' is-selected' : ''}`}
      style={{ borderColor: accent }}
    >
      <Handle type="target" position={Position.Top} className="tt-rf-handle" />
      <div className="tt-rf-node-row">
        <span className="tt-rf-node-kind" style={{ background: accent }}>
          PERSON
        </span>
        {typeof node.data.trustScore === 'number' && (
          <span className="tt-rf-node-badge" style={{ color: accent }}>
            {node.data.trustScore}
          </span>
        )}
      </div>
      <div className="tt-rf-node-title">{node.label}</div>
      <div className="tt-rf-node-sub">
        {node.data.role || 'Unknown role'} · {riskLabel(risk)}
      </div>
      <Handle type="source" position={Position.Bottom} className="tt-rf-handle" />
    </div>
  );
}

function EventNode({ data }: NodeProps<Node<EventNodeData>>) {
  const { node, isSelected } = data;
  const accent = eventRiskColor(node.data.riskLevel, node.data.risk);
  return (
    <div
      className={`tt-rf-node tt-rf-event${isSelected ? ' is-selected' : ''}`}
      style={{ borderColor: accent }}
    >
      <Handle type="target" position={Position.Top} className="tt-rf-handle" />
      <div className="tt-rf-node-row">
        <span className="tt-rf-node-kind" style={{ background: accent }}>
          EVENT
        </span>
        <span className="tt-rf-node-badge" style={{ color: accent }}>
          R{node.data.riskLevel ?? '—'}
        </span>
      </div>
      <div className="tt-rf-node-title">{truncate(node.label, 56)}</div>
      <div className="tt-rf-node-sub">
        {node.data.eventCategory || node.data.eventType || 'Event'}
      </div>
      <Handle type="source" position={Position.Bottom} className="tt-rf-handle" />
    </div>
  );
}

const NODE_TYPES = {
  company: CompanyNode,
  person: PersonNode,
  event: EventNode,
};

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

/* ------------------------------------------------------------------ */
/* Layout                                                              */
/* ------------------------------------------------------------------ */

function layoutGraph(
  nodes: EntityGraphNode[],
  edges: EntityGraphEdge[]
): {
  positions: Map<string, { x: number; y: number }>;
  sizes: Map<string, { width: number; height: number }>;
  order: Map<string, number>;
} {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: 'TB',
    nodesep: 120,
    edgesep: 40,
    ranksep: 150,
    marginx: 40,
    marginy: 40,
    ranker: 'tight-tree',
    acyclicer: 'greedy',
  });

  const sizes = new Map<string, { width: number; height: number }>();
  for (const node of nodes) {
    const size = estimateNodeSize(node);
    sizes.set(node.id, size);
    g.setNode(node.id, { ...size, rank: node.depth });
  }

  const depthById = new Map(nodes.map((node) => [node.id, node.depth]));
  for (const edge of edges) {
    const sourceDepth = depthById.get(edge.source) ?? 0;
    const targetDepth = depthById.get(edge.target) ?? sourceDepth + 1;
    g.setEdge(edge.source, edge.target, {
      minlen: Math.max(1, targetDepth - sourceDepth),
      weight: edge.relationshipType === 'CONNECTION' ? 3 : 2,
    });
  }

  dagre.layout(g);

  const positions = new Map<string, { x: number; y: number }>();
  const order = new Map<string, number>();
  let i = 0;
  for (const node of nodes) {
    const placed = g.node(node.id);
    const size = sizes.get(node.id)!;
    if (!placed) continue;
    positions.set(node.id, {
      x: placed.x - size.width / 2,
      y: placed.y - size.height / 2,
    });
    order.set(node.id, i++);
  }
  return { positions, sizes, order };
}

/* ------------------------------------------------------------------ */
/* Detail drawer                                                       */
/* ------------------------------------------------------------------ */

function CompanyDetailRows(node: Extract<EntityGraphNode, { entityType: 'Company' }>) {
  const risk: Risk = node.data.risk ?? 'low';
  return (
    <>
      <Row label="Type">Company</Row>
      <Row label="Trust score">{node.data.score ?? '—'}</Row>
      <Row label="Risk">{riskLabel(risk)}</Row>
      <Row label="Sector">{node.data.sector ?? '—'}</Row>
      <Row label="Country">{node.data.country ?? '—'}</Row>
      <Row label="NIP">{node.data.nip || '—'}</Row>
      <Row label="Articles">{node.data.articles ?? '—'}</Row>
      <Row label="Keywords">
        {(node.data.keywords ?? []).slice(0, 5).join(', ') || '—'}
      </Row>
    </>
  );
}

function PersonDetailRows(node: Extract<EntityGraphNode, { entityType: 'Person' }>) {
  const risk: Risk = node.data.risk ?? 'low';
  return (
    <>
      <Row label="Type">Person</Row>
      <Row label="Trust score">{node.data.trustScore ?? '—'}</Row>
      <Row label="Risk">{riskLabel(risk)}</Row>
      <Row label="Role">{node.data.role || '—'}</Row>
      <Row label="Affiliation">{node.data.firmName || '—'}</Row>
      <Row label="Events">{node.data.eventCount ?? '—'}</Row>
      <Row label="Description" stack>
        {node.data.description || '—'}
      </Row>
    </>
  );
}

function EventDetailRows(node: Extract<EntityGraphNode, { entityType: 'Event' }>) {
  return (
    <>
      <Row label="Type">Event</Row>
      <Row label="Category">{node.data.eventCategory || '—'}</Row>
      <Row label="Subtype">{node.data.eventType || '—'}</Row>
      <Row label="Risk">{node.data.riskLevel ?? '—'} / 10</Row>
      <Row label="Risk class">{riskLabel(node.data.risk ?? riskFromLevel(node.data.riskLevel))}</Row>
      <Row label="Occurred">{node.data.occurredAt || '—'}</Row>
      <Row label="Company">{node.data.companyName || '—'}</Row>
      <Row label="Source">{node.data.sourceTitle || node.data.source || '—'}</Row>
      {node.data.sourceUrl && (
        <Row label="URL" stack>
          <a href={node.data.sourceUrl} target="_blank" rel="noreferrer" className="tt-rf-link">
            {node.data.sourceUrl}
          </a>
        </Row>
      )}
      <Row label="Keywords">
        {(node.data.keywords ?? []).slice(0, 5).join(', ') || '—'}
      </Row>
      <Row label="Excerpt" stack>
        {node.data.excerpt || '—'}
      </Row>
    </>
  );
}

function Row({
  label,
  children,
  stack = false,
}: {
  label: string;
  children: React.ReactNode;
  stack?: boolean;
}) {
  return (
    <div className={`tt-rf-kv${stack ? ' is-stack' : ''}`}>
      <span className="tt-rf-kv-label">{label}</span>
      <span className="tt-rf-kv-value">{children}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Legend                                                              */
/* ------------------------------------------------------------------ */

function Legend() {
  return (
    <div className="tt-rf-legend">
      <div className="tt-rf-legend-section">
        <div className="tt-rf-legend-title">Nodes</div>
        <div className="tt-rf-legend-items">
          <span className="tt-rf-legend-item">
            <span className="tt-rf-swatch tt-rf-swatch-company" />
            <span className="tt-rf-legend-copy">
              <span className="tt-rf-legend-name">Company</span>
              <span className="tt-rf-legend-desc">risk + trust</span>
            </span>
          </span>
          <span className="tt-rf-legend-item">
            <span className="tt-rf-swatch tt-rf-swatch-person" />
            <span className="tt-rf-legend-copy">
              <span className="tt-rf-legend-name">Person</span>
              <span className="tt-rf-legend-desc">risk + trust</span>
            </span>
          </span>
          <span className="tt-rf-legend-item">
            <span className="tt-rf-swatch tt-rf-swatch-event" />
            <span className="tt-rf-legend-copy">
              <span className="tt-rf-legend-name">Event</span>
              <span className="tt-rf-legend-desc">risk class + R0–R10</span>
            </span>
          </span>
        </div>
      </div>
      <div className="tt-rf-legend-section">
        <div className="tt-rf-legend-title">Edges</div>
        <div className="tt-rf-legend-items">
          {(Object.entries(EDGE_STYLE) as Array<
            [EntityGraphEdge['relationshipType'], (typeof EDGE_STYLE)[EntityGraphEdge['relationshipType']]]
          >).map(([type, style]) => (
            <span key={type} className="tt-rf-legend-item">
              <svg width="38" height="10" viewBox="0 0 38 10" aria-hidden="true">
                <title>{style.label} edge style</title>
                <line
                  x1="2"
                  y1="5"
                  x2="36"
                  y2="5"
                  stroke={style.stroke}
                  strokeWidth={style.strokeWidth}
                  strokeDasharray={style.strokeDasharray}
                  strokeLinecap="round"
                />
              </svg>
              <span className="tt-rf-legend-copy">
                <span className="tt-rf-legend-name">{style.label}</span>
                <span className="tt-rf-legend-desc">{style.description}</span>
              </span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

function classifierForEntityType(type: string): string {
  switch (type) {
    case 'Person': return 'NSA';
    case 'Event': return 'Tarkov';
    case 'Company': return 'Market';
    default: return 'EEM';
  }
}

function CompanyGraphInner({ company, graph, onSelectCompany }: CompanyGraphProps) {
  const baseModel = useMemo(() => normalizeEntityGraph(graph), [graph]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [localRootId, setLocalRootId] = useState<string>(baseModel.rootId);
  const [traceOpen, setTraceOpen] = useState(false);

  useEffect(() => {
    setLocalRootId(baseModel.rootId);
    setSelectedId(null);
  }, [baseModel.rootId]);

  const model = useMemo(() => rerootEntityGraph(baseModel, localRootId), [baseModel, localRootId]);

  const { positions, sizes } = useMemo(
    () => layoutGraph(model.nodes, model.edges),
    [model.edges, model.nodes]
  );

  const rfNodes: Node[] = useMemo(
    () =>
      model.nodes.map((node) => {
        const pos = positions.get(node.id) ?? { x: 0, y: 0 };
        const size = sizes.get(node.id);
        const isRoot = node.id === model.rootId;
        const isSelected = selectedId === node.id;

        const base = {
          id: node.id,
          position: pos,
          draggable: true,
          selectable: true,
          ...(size ? { width: size.width, height: size.height } : {}),
        };

        if (node.entityType === 'Company') {
          return { ...base, type: 'company', data: { node, isRoot, isSelected } };
        }
        if (node.entityType === 'Person') {
          return { ...base, type: 'person', data: { node, isSelected, risk: node.data.risk ?? 'low' } };
        }
        return { ...base, type: 'event', data: { node, isSelected } };
      }),
    [model.nodes, model.rootId, positions, sizes, selectedId]
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      model.edges.map((edge) => {
        const style = EDGE_STYLE[edge.relationshipType];
        const isHighlighted =
          selectedId !== null && (edge.source === selectedId || edge.target === selectedId);
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: 'smoothstep',
          pathOptions: { borderRadius: 18, offset: 24 },
          animated: edge.relationshipType === 'INVOLVED_IN',
          label:
            isHighlighted || model.edges.length <= 5
              ? truncate(edge.connectionType || edge.label || style.label, 24)
              : undefined,
          labelStyle: { fontSize: 10, fill: 'var(--tt-fg-soft)' },
          labelBgStyle: { fill: 'var(--tt-bg-card)', fillOpacity: 0.98 },
          labelBgPadding: [6, 3] as [number, number],
          labelBgBorderRadius: 4,
          style: {
            stroke: style.stroke,
            strokeWidth: isHighlighted ? style.strokeWidth + 1 : style.strokeWidth,
            strokeDasharray: style.strokeDasharray,
            opacity: selectedId === null || isHighlighted ? 1 : 0.18,
          },
          zIndex: isHighlighted ? 2 : 0,
          data: { edge },
        };
      }),
    [model.edges, selectedId]
  );

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedId(node.id);
  }, []);

  const onNodeDoubleClick: NodeMouseHandler = useCallback(
    (_, node) => {
      setLocalRootId(node.id);
      setSelectedId(node.id);
    },
    []
  );

  const onPaneClick = useCallback(() => setSelectedId(null), []);

  const selectedNode = useMemo(
    () => model.nodes.find((node) => node.id === selectedId) ?? null,
    [model.nodes, selectedId]
  );

  if (model.nodes.length <= 1 || model.edges.length === 0) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">
          No related companies, people or events found for {company.short}.
        </div>
      </div>
    );
  }

  return (
    <div className="tt-rf-shell">
      <Legend />
      <div className="tt-rf-stage">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={NODE_TYPES}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={onNodeDoubleClick}
          onPaneClick={onPaneClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="oklch(0.9 0.01 250)" />
          <Controls position="bottom-right" showInteractive={false} />
          <MiniMap
            position="top-right"
            pannable
            zoomable
            nodeStrokeWidth={2}
            nodeColor={(node) => {
              const original = model.nodes.find((entry) => entry.id === node.id);
              if (!original) return '#ccc';
              if (original.entityType === 'Company') return riskColor(original.data.risk ?? 'low');
              if (original.entityType === 'Event') return eventRiskColor(original.data.riskLevel, original.data.risk);
              return riskColor(original.data.risk ?? 'low');
            }}
            style={{ border: '1px solid var(--tt-line)', borderRadius: 6 }}
          />
        </ReactFlow>
      </div>

      {selectedNode && (
        <aside className="tt-rf-drawer" role="dialog" aria-label="Node details">
          <header className="tt-rf-drawer-head">
            <div>
              <div className="tt-rf-drawer-kind">{selectedNode.entityType.toUpperCase()}</div>
              <div className="tt-rf-drawer-title">{selectedNode.label}</div>
              <div className="tt-rf-drawer-sub">{selectedNode.summary}</div>
            </div>
            <button
              type="button"
              className="tt-rf-drawer-close"
              onClick={() => setSelectedId(null)}
              aria-label="Close details"
            >
              ×
            </button>
          </header>
          <div className="tt-rf-drawer-body">
            {selectedNode.entityType === 'Company' && CompanyDetailRows(selectedNode)}
            {selectedNode.entityType === 'Person' && PersonDetailRows(selectedNode)}
            {selectedNode.entityType === 'Event' && EventDetailRows(selectedNode)}
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                className="tt-btn-ghost tt-btn-trace"
                onClick={() => setTraceOpen(true)}
              >
                Pokaż trace
              </button>
            </div>
          </div>
          {(selectedNode.id !== model.rootId || selectedNode.entityType === 'Company') && (
            <footer className="tt-rf-drawer-foot">
              {selectedNode.id !== model.rootId && (
                <button
                  type="button"
                  className="tt-rf-drawer-action"
                  onClick={() => setLocalRootId(selectedNode.id)}
                >
                  Use as graph root
                </button>
              )}
              {selectedNode.entityType === 'Company' && selectedNode.id !== model.rootId && (
                <div className="tt-rf-drawer-hint">Local graph root and company navigation are separate now.</div>
              )}
              {selectedNode.entityType === 'Company' && selectedNode.id === model.rootId && (
                <div className="tt-rf-drawer-hint">This company is the current graph root.</div>
              )}
              {selectedNode.entityType !== 'Company' && (
                <div className="tt-rf-drawer-hint">Tip: double-click any node to re-center the graph.</div>
              )}
              {selectedNode.entityType === 'Company' && (
                <button
                  type="button"
                  className="tt-rf-drawer-action is-secondary"
                  onClick={() => {
                    const target = selectedNode.data.id ?? selectedNode.entityId;
                    if (target) onSelectCompany(target);
                  }}
                >
                  Open company record
                </button>
              )}
            </footer>
          )}
        </aside>
      )}

      {selectedNode && (
        <TraceDrawer
          open={traceOpen}
          onClose={() => setTraceOpen(false)}
          classifier={classifierForEntityType(selectedNode.entityType)}
          entityId={selectedNode.entityId}
        />
      )}
    </div>
  );
}

export function CompanyGraph(props: CompanyGraphProps) {
  return (
    <ReactFlowProvider>
      <CompanyGraphInner {...props} />
    </ReactFlowProvider>
  );
}
