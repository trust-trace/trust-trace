'use client';

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceRadial,
  forceSimulation,
  drag as d3Drag,
  select,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3';
import { buildCompanyGraph } from '@/lib/company-graph';
import type {
  Company,
  CompanyRelation,
  GraphRelationType,
} from '@/lib/data';
import { riskColor } from './sidebar';

/* ---------------------------------------------------------------- */
/* Types                                                             */
/* ---------------------------------------------------------------- */

interface CompanyGraphProps {
  company: Company;
  companies: Company[];
  relations: CompanyRelation[];
  onSelectCompany: (id: string) => void;
}

interface SimNode extends SimulationNodeDatum {
  id: string;
  company: Company;
  depth: number;
}

interface SimEdge extends SimulationLinkDatum<SimNode> {
  source: string | SimNode;
  target: string | SimNode;
  type: GraphRelationType;
  label?: string;
}

interface Snapshot {
  nodes: Array<{ id: string; company: Company; depth: number; x: number; y: number }>;
  edges: Array<{
    sourceId: string;
    targetId: string;
    sx: number;
    sy: number;
    tx: number;
    ty: number;
    type: GraphRelationType;
    label?: string;
  }>;
}

/* ---------------------------------------------------------------- */
/* Constants                                                         */
/* ---------------------------------------------------------------- */

const W = 920;
const H = 560;
const CX = W / 2;
const CY = H / 2;

/* ---------------------------------------------------------------- */
/* Helpers                                                           */
/* ---------------------------------------------------------------- */

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

function relationDash(type: GraphRelationType): string {
  if (type === 'person') return '6 3';
  if (type === 'partnership') return '2 3';
  return '';
}

function nodeRadius(depth: number): number {
  if (depth === 0) return 38;
  if (depth === 1) return 26;
  return 19;
}

function snap(simNodes: SimNode[], simEdges: SimEdge[]): Snapshot {
  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));
  return {
    nodes: simNodes.map((n) => ({
      id: n.id,
      company: n.company,
      depth: n.depth,
      x: n.x ?? CX,
      y: n.y ?? CY,
    })),
    edges: simEdges.map((e) => {
      const s = typeof e.source === 'object' ? e.source : nodeMap.get(e.source as string);
      const t = typeof e.target === 'object' ? e.target : nodeMap.get(e.target as string);
      return {
        sourceId: typeof e.source === 'object' ? e.source.id : (e.source as string),
        targetId: typeof e.target === 'object' ? e.target.id : (e.target as string),
        sx: s?.x ?? CX,
        sy: s?.y ?? CY,
        tx: t?.x ?? CX,
        ty: t?.y ?? CY,
        type: e.type,
        label: e.label,
      };
    }),
  };
}

/* ---------------------------------------------------------------- */
/* Component                                                         */
/* ---------------------------------------------------------------- */

export function CompanyGraph({
  company,
  companies,
  relations,
  onSelectCompany,
}: CompanyGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<ReturnType<typeof forceSimulation<SimNode>> | null>(null);
  const simNodesRef = useRef<SimNode[]>([]);
  const simEdgesRef = useRef<SimEdge[]>([]);

  const uid = useId();
  const glowId = `${uid}-glow`;
  const bgGradId = `${uid}-bg`;

  const [snapshot, setSnapshot] = useState<Snapshot>({ nodes: [], edges: [] });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeKey, setHoveredEdgeKey] = useState<string | null>(null);
  const [entered, setEntered] = useState(false);

  const graph = useMemo(
    () => buildCompanyGraph(company.id, companies, relations, 2),
    [company.id, companies, relations]
  );

  const graphNodes = graph.nodes;
  const graphEdges = graph.edges;
  const centerId = graph.centerId;

  /* ---------- simulation lifecycle ---------- */

  const onTick = useCallback(() => {
    setSnapshot(snap(simNodesRef.current, simEdgesRef.current));
  }, []);

  useEffect(() => {
    simRef.current?.stop();

    const nodes: SimNode[] = graphNodes.map((n, i) => {
      const angle = (i / Math.max(graphNodes.length, 1)) * Math.PI * 2;
      const r = n.depth === 0 ? 0 : n.depth === 1 ? 160 : 290;
      return { ...n, x: CX + Math.cos(angle) * r, y: CY + Math.sin(angle) * r };
    });

    const edges: SimEdge[] = graphEdges.map((e) => ({ ...e }));

    simNodesRef.current = nodes;
    simEdgesRef.current = edges;

    const sim = forceSimulation<SimNode>(nodes)
      .force(
        'link',
        forceLink<SimNode, SimEdge>(edges)
          .id((n) => n.id)
          .distance((l) => {
            const sd = typeof l.source === 'object' ? l.source.depth : 0;
            const td = typeof l.target === 'object' ? l.target.depth : 0;
            return Math.max(sd, td) === 1 ? 170 : 140;
          })
          .strength(0.7)
      )
      .force('charge', forceManyBody().strength(-800))
      .force('collide', forceCollide<SimNode>().radius((n) => nodeRadius(n.depth) + 18))
      .force('center', forceCenter(CX, CY).strength(0.05))
      .force(
        'radial',
        forceRadial<SimNode>(
          (n) => (n.depth === 0 ? 0 : n.depth === 1 ? 160 : 290),
          CX,
          CY
        ).strength(0.6)
      )
      .alpha(1)
      .alphaDecay(0.02)
      .velocityDecay(0.35)
      .on('tick', onTick);

    const center = nodes.find((n) => n.id === centerId);
    if (center) {
      center.fx = CX;
      center.fy = CY;
    }

    simRef.current = sim;

    const timeout = setTimeout(() => setEntered(true), 60);

    return () => {
      sim.stop();
      clearTimeout(timeout);
      setEntered(false);
    };
  }, [graphNodes, graphEdges, centerId, onTick]);

  /* ---------- drag ---------- */

  useEffect(() => {
    const svg = svgRef.current;
    const sim = simRef.current;
    if (!svg || !sim) return;

    const dragBehavior = d3Drag<SVGCircleElement, SimNode>()
      .on('start', (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        if (d.id !== company.id) {
          d.fx = null;
          d.fy = null;
        }
      });

    select(svg)
      .selectAll<SVGCircleElement, SimNode>('.tt-graph-node-hit')
      .data(simNodesRef.current)
      .call(dragBehavior);
  }, [company.id, snapshot]);

  /* ---------- derived from snapshot ---------- */

  const hoveredNode = hoveredNodeId
    ? snapshot.nodes.find((n) => n.id === hoveredNodeId) ?? null
    : null;
  const hoveredEdge = hoveredEdgeKey
    ? snapshot.edges.find(
        (e) => `${e.sourceId}:${e.targetId}:${e.type}` === hoveredEdgeKey
      ) ?? null
    : null;

  /* ---------- empty state ---------- */

  if (graph.nodes.length <= 1 || graph.edges.length === 0) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">
          Brak zdefiniowanych relacji dla {company.short}.
        </div>
      </div>
    );
  }

  /* ---------- render ---------- */

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
                {hoveredNode.company.sector} ·{' '}
                {hoveredNode.depth === 0
                  ? 'Firma centralna'
                  : hoveredNode.depth === 1
                    ? 'Połączenie bezpośrednie'
                    : 'Poziom 2'}
                {' · Trust '}
                <span style={{ color: riskColor(hoveredNode.company.risk) }}>
                  {hoveredNode.company.score}
                </span>
              </div>
            </>
          )}
          {!hoveredNode && hoveredEdge && (
            <>
              <div className="tt-graph-detail-title">{relationLabel(hoveredEdge.type)}</div>
              <div className="tt-graph-detail-sub">{hoveredEdge.label ?? 'Brak dodatkowego opisu'}</div>
            </>
          )}
          {!hoveredNode && !hoveredEdge && (
            <>
              <div className="tt-graph-detail-title">{company.short} &middot; mapa relacji</div>
              <div className="tt-graph-detail-sub">
                Przeciągnij węzły, aby zmienić układ. Kliknij firmę, aby przełączyć kontekst.
              </div>
            </>
          )}
        </div>
      </div>

      <div className="tt-graph-stage">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="tt-graph-svg"
          aria-label={`Graf relacji dla ${company.name}`}
        >
          <title>{`Graf relacji dla ${company.name}`}</title>

          <defs>
            <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id={bgGradId}>
              <stop offset="0%" stopColor="oklch(0.97 0.012 250)" stopOpacity="0.5" />
              <stop offset="100%" stopColor="oklch(0.97 0.012 250)" stopOpacity="0" />
            </radialGradient>
          </defs>

          <circle cx={CX} cy={CY} r="220" fill={`url(#${bgGradId})`} />

          {/* edges */}
          {snapshot.edges.map((edge) => {
            const key = `${edge.sourceId}:${edge.targetId}:${edge.type}`;
            const isHovered = hoveredEdgeKey === key;
            const isConnected =
              hoveredNodeId !== null &&
              (edge.sourceId === hoveredNodeId || edge.targetId === hoveredNodeId);
            const dimmed = hoveredNodeId !== null && !isConnected && !isHovered;

            return (
              <line
                key={key}
                className={`tt-graph-edge${entered ? ' tt-entered' : ''}`}
                x1={edge.sx}
                y1={edge.sy}
                x2={edge.tx}
                y2={edge.ty}
                stroke={relationColor(edge.type)}
                strokeWidth={isHovered ? 3 : isConnected ? 2.5 : 1.5}
                strokeOpacity={dimmed ? 0.15 : isHovered ? 0.95 : 0.5}
                strokeDasharray={relationDash(edge.type)}
                onMouseEnter={() => setHoveredEdgeKey(key)}
                onMouseLeave={() => setHoveredEdgeKey((c) => (c === key ? null : c))}
              >
                <title>{`${relationLabel(edge.type)}${edge.label ? ` · ${edge.label}` : ''}`}</title>
              </line>
            );
          })}

          {/* nodes */}
          {snapshot.nodes.map((node, idx) => {
            const active = node.id === company.id;
            const r = nodeRadius(node.depth);
            const fill = active ? 'oklch(0.18 0.02 260)' : riskColor(node.company.risk);
            const strokeCol = active ? riskColor(node.company.risk) : 'oklch(1 0 0 / 0.85)';
            const isHovered = hoveredNodeId === node.id;
            const dimmed =
              hoveredNodeId !== null &&
              !isHovered &&
              !snapshot.edges.some(
                (e) =>
                  (e.sourceId === hoveredNodeId && e.targetId === node.id) ||
                  (e.targetId === hoveredNodeId && e.sourceId === node.id)
              );

            return (
              <g
                key={node.id}
                className={`tt-graph-node${entered ? ' tt-entered' : ''}`}
                style={{ animationDelay: `${idx * 60}ms` }}
                transform={`translate(${node.x}, ${node.y})`}
                opacity={dimmed ? 0.3 : 1}
              >
                <title>{`Wybierz firmę ${node.company.name}`}</title>

                {isHovered && (
                  <circle
                    className="tt-graph-glow"
                    r={r + 8}
                    fill="none"
                    stroke={fill}
                    strokeWidth={2}
                    strokeOpacity={0.3}
                    filter={`url(#${glowId})`}
                  />
                )}

                {active && (
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke={riskColor(node.company.risk)}
                    strokeWidth={1}
                    strokeOpacity={0.25}
                    strokeDasharray="3 4"
                  />
                )}

                <circle
                  className="tt-graph-node-hit"
                  r={r}
                  fill={fill}
                  stroke={strokeCol}
                  strokeWidth={active ? 3 : isHovered ? 3 : 2}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId((c) => (c === node.id ? null : c))}
                  onClick={() => onSelectCompany(node.id)}
                />

                {!active && node.depth <= 1 && (
                  <g transform={`translate(${r * 0.65}, ${-r * 0.65})`}>
                    <circle r={9} fill="var(--tt-bg-card)" stroke="var(--tt-line)" strokeWidth={1} />
                    <text className="tt-graph-score-badge" textAnchor="middle" y={3.5} fill={riskColor(node.company.risk)}>
                      {node.company.score}
                    </text>
                  </g>
                )}

                <text className="tt-graph-node-label" textAnchor="middle" y={r + 16} fill="var(--tt-fg)">
                  {node.company.short}
                </text>

                {active && (
                  <text className="tt-graph-node-sub" textAnchor="middle" y={r + 28} fill="var(--tt-fg-mute)">
                    Trust {node.company.score}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
