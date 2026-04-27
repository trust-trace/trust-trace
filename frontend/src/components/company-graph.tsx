'use client';

import { useMemo, useState } from 'react';
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceRadial,
  forceSimulation,
} from 'd3';
import { buildCompanyGraph } from '@/lib/company-graph';
import type {
  Company,
  CompanyRelation,
  GraphRelationType,
} from '@/lib/data';
import { riskColor } from './sidebar';

interface CompanyGraphProps {
  company: Company;
  companies: Company[];
  relations: CompanyRelation[];
  onSelectCompany: (id: string) => void;
}

interface LayoutNode {
  id: string;
  company: Company;
  depth: number;
  x: number;
  y: number;
  fx?: number;
  fy?: number;
}

const GRAPH_WIDTH = 920;
const GRAPH_HEIGHT = 560;
const GRAPH_CENTER_X = GRAPH_WIDTH / 2;
const GRAPH_CENTER_Y = GRAPH_HEIGHT / 2;

function relationLabel(type: GraphRelationType): string {
  if (type === 'person') return 'Powiązanie osobowe';
  if (type === 'partnership') return 'Współpraca';
  return 'Relacja biznesowa';
}

function relationColor(type: GraphRelationType): string {
  if (type === 'person') return 'oklch(0.57 0.16 20)';
  if (type === 'partnership') return 'oklch(0.64 0.14 82)';
  return 'oklch(0.53 0.12 240)';
}

function nodeRadius(depth: number): number {
  if (depth === 0) return 36;
  if (depth === 1) return 24;
  return 18;
}

export function CompanyGraph({ company, companies, relations, onSelectCompany }: CompanyGraphProps) {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const graph = useMemo(
    () => buildCompanyGraph(company.id, companies, relations, 2),
    [company.id, companies, relations]
  );

  const layout = useMemo(() => {
    const depthById = new Map(graph.nodes.map((node) => [node.id, node.depth]));
    const getLinkDepth = (value: unknown): number => {
      if (typeof value === 'object' && value !== null && 'depth' in value) {
        return Number(value.depth) || 0;
      }

      return typeof value === 'string' ? (depthById.get(value) ?? 0) : 0;
    };

    const nodes: LayoutNode[] = graph.nodes.map((node, index) => {
      const angle = (index / Math.max(graph.nodes.length, 1)) * Math.PI * 2;
      const radius = node.depth === 0 ? 0 : node.depth === 1 ? 150 : 270;

      return {
        ...node,
        x: GRAPH_CENTER_X + Math.cos(angle) * radius,
        y: GRAPH_CENTER_Y + Math.sin(angle) * radius,
      };
    });

    const simulation = forceSimulation(nodes)
      .force(
        'link',
        forceLink(
          graph.edges.map((edge) => ({ ...edge }))
        )
          .id((node) => (node as LayoutNode).id)
          .distance((link) => {
            const sourceDepth = getLinkDepth(link.source);
            const targetDepth = getLinkDepth(link.target);
            return Math.max(sourceDepth, targetDepth) === 1 ? 160 : 135;
          })
          .strength(0.9)
      )
      .force('charge', forceManyBody().strength(-900))
      .force('collide', forceCollide<LayoutNode>().radius((node) => nodeRadius(node.depth) + 28))
      .force('center', forceCenter(GRAPH_CENTER_X, GRAPH_CENTER_Y))
      .force(
        'radial',
        forceRadial<LayoutNode>(
          (node) => (node.depth === 0 ? 0 : node.depth === 1 ? 155 : 280),
          GRAPH_CENTER_X,
          GRAPH_CENTER_Y
        ).strength(0.9)
      )
      .stop();

    const centerNode = nodes.find((node) => node.id === graph.centerId);
    if (centerNode) {
      centerNode.fx = GRAPH_CENTER_X;
      centerNode.fy = GRAPH_CENTER_Y;
    }

    for (let tick = 0; tick < 240; tick += 1) {
      simulation.tick();
    }

    simulation.stop();

    return nodes;
  }, [graph.centerId, graph.edges, graph.nodes]);

  const positionedNodes = new Map(layout.map((node) => [node.id, node]));
  const hoveredNode = hoveredNodeId ? positionedNodes.get(hoveredNodeId) ?? null : null;

  if (graph.nodes.length <= 1 || graph.edges.length === 0) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">
          Brak zdefiniowanych relacji dla {company.short}. Dodaj mockowane powiązania, aby zbudować mapę firm.
        </div>
      </div>
    );
  }

  return (
    <div className="tt-graph-shell">
      <div className="tt-graph-meta">
        <div className="tt-graph-legend">
          {(['person', 'partnership', 'business'] as const).map((type) => (
            <div key={type} className="tt-graph-legend-item">
              <span className="tt-graph-legend-line" style={{ background: relationColor(type) }} />
              <span>{relationLabel(type)}</span>
            </div>
          ))}
        </div>

        <div className="tt-graph-detail">
          {hoveredNode && (
            <>
              <div className="tt-graph-detail-title">{hoveredNode.company.name}</div>
              <div className="tt-graph-detail-sub">
                {hoveredNode.depth === 0
                  ? 'Firma centralna'
                  : hoveredNode.depth === 1
                    ? 'Połączenie bezpośrednie'
                    : 'Połączenie drugiego poziomu'}
              </div>
            </>
          )}
          {!hoveredNode && (
            <>
              <div className="tt-graph-detail-title">{company.short} jako węzeł centralny</div>
              <div className="tt-graph-detail-sub">Najedź na węzeł, aby podejrzeć pozycję firmy w grafie. Kliknięcie firmy przełącza kontekst.</div>
            </>
          )}
        </div>
      </div>

      <div className="tt-graph-stage">
        <svg
          viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
          className="tt-graph-svg"
          aria-label={`Graf relacji dla ${company.name}`}
        >
          <title>{`Graf relacji dla ${company.name}`}</title>
          {graph.edges.map((edge) => {
            const source = positionedNodes.get(edge.source);
            const target = positionedNodes.get(edge.target);
            if (!source || !target) return null;

            const edgeKey = `${edge.source}:${edge.target}:${edge.type}`;

            return (
              <line
                key={edgeKey}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={relationColor(edge.type)}
                strokeWidth={2}
                strokeOpacity={0.56}
              >
                <title>{`${relationLabel(edge.type)}${edge.label ? ` · ${edge.label}` : ''}`}</title>
              </line>
            );
          })}

          {layout.map((node) => {
            const active = node.id === company.id;
            const fill = active ? 'oklch(0.18 0.02 260)' : riskColor(node.company.risk);
            const stroke = active ? riskColor(node.company.risk) : 'oklch(1 0 0 / 0.82)';

            return (
              <g
                key={node.id}
                className="tt-graph-node"
                transform={`translate(${node.x}, ${node.y})`}
              >
                <title>{`Wybierz firmę ${node.company.name}`}</title>
                <circle
                  className="tt-graph-node-hit"
                  r={nodeRadius(node.depth)}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={active ? 3 : 2}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId((current) => (current === node.id ? null : current))}
                  onClick={() => onSelectCompany(node.id)}
                />
                <text
                  className="tt-graph-node-label"
                  textAnchor="middle"
                  y={node.depth === 0 ? 5 : 4}
                  fill={active ? 'white' : 'var(--tt-fg)'}
                  pointerEvents="none"
                >
                  {node.company.short}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
