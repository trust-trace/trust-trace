'use client';

import { useEffect, useMemo, useState } from 'react';

import { getNeo4jGraph } from '@/lib/api';
import { type Neo4jGraphNode, type Neo4jGraphPayload } from '@/lib/neo4j-graph';

const W = 920;
const H = 560;
const CX = W / 2;
const CY = H / 2;

type GraphStatus = 'loading' | 'error' | 'success';

interface PositionedNode extends Neo4jGraphNode {
  x: number;
  y: number;
}

function nodeColor(kind: Neo4jGraphNode['kind']): string {
  if (kind === 'company') return 'oklch(0.22 0.03 255)';
  if (kind === 'person') return 'oklch(0.62 0.12 210)';
  return 'oklch(0.72 0.1 30)';
}

function edgeColor(type: string): string {
  if (type === 'ABOUT') return 'oklch(0.65 0.08 35)';
  if (type === 'INVOLVED_IN') return 'oklch(0.62 0.1 220)';
  if (type === 'AFFILIATED_WITH') return 'oklch(0.6 0.12 145)';
  return 'oklch(0.58 0.08 300)';
}

function nodeRadius(kind: Neo4jGraphNode['kind']): number {
  if (kind === 'company') return 28;
  if (kind === 'person') return 20;
  return 16;
}

function positionNodes(nodes: Neo4jGraphNode[]): PositionedNode[] {
  return nodes.map((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    const radius = node.kind === 'company' ? 180 : node.kind === 'person' ? 250 : 320;
    return {
      ...node,
      x: CX + Math.cos(angle) * radius,
      y: CY + Math.sin(angle) * radius,
    };
  });
}

export function Neo4jGraph() {
  const [status, setStatus] = useState<GraphStatus>('loading');
  const [graph, setGraph] = useState<Neo4jGraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getNeo4jGraph()
      .then((payload) => {
        if (cancelled) return;
        setGraph(payload);
        setStatus('success');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return <Neo4jGraphView status={status} graph={graph} error={error} />;
}

interface Neo4jGraphViewProps {
  status: GraphStatus;
  graph: Neo4jGraphPayload | null;
  error: string | null;
}

export function Neo4jGraphView({ status, graph, error }: Neo4jGraphViewProps) {
  if (status === 'loading') {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Ładowanie grafu...</div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Nie udało się załadować grafu: {error}</div>
      </div>
    );
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Brak danych grafowych w Neo4j.</div>
      </div>
    );
  }

  const positionedNodes = positionNodes(graph.nodes);
  const nodesById = new Map(positionedNodes.map((node) => [node.id, node]));

  return (
    <div className="tt-graph-shell">
      <div className="tt-graph-meta">
        <div className="tt-graph-detail">
          <div className="tt-graph-detail-title">Graf Neo4j</div>
          <div className="tt-graph-detail-sub">Firmy, osoby, zdarzenia i relacje z backendu.</div>
        </div>
      </div>

      <div className="tt-graph-stage">
        <svg viewBox={`0 0 ${W} ${H}`} className="tt-graph-svg" aria-label="Graf Neo4j">
          <title>Graf Neo4j</title>
          {graph.edges.map((edge) => {
            const source = nodesById.get(edge.source);
            const target = nodesById.get(edge.target);
            if (!source || !target) return null;

            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={edgeColor(edge.type)}
                strokeOpacity={0.6}
                strokeWidth={2}
              />
            );
          })}

          {positionedNodes.map((node) => {
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                opacity={1}
              >
                <circle
                  r={nodeRadius(node.kind)}
                  fill={nodeColor(node.kind)}
                  stroke="oklch(1 0 0 / 0.9)"
                  strokeWidth={2}
                />
                <text className="tt-graph-node-label" textAnchor="middle" y={nodeRadius(node.kind) + 16} fill="var(--tt-fg)">
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
