'use client';

import { useId } from 'react';

import type { HistoryRangeKey } from '@/lib/data';

interface ScoreChartProps {
  history: number[];
  color: string;
  range: HistoryRangeKey;
}

const LABELS_BY_RANGE: Record<HistoryRangeKey, string[]> = {
  '12M': ['M-11', 'M-9', 'M-7', 'M-5', 'M-3', 'now'],
  '6M': ['M-5', 'M-4', 'M-3', 'M-2', 'M-1', 'now'],
  '3M': ['M-2', 'M-1', 'M-1', 'M-0', 'M-0', 'now'],
  '30D': ['D-30', 'D-24', 'D-18', 'D-12', 'D-6', 'now'],
};

export function ScoreChart({ history, color, range: chartRange }: ScoreChartProps) {
  const gradId = useId();
  const W = 640;
  const H = 120;
  const PAD = 16;
  const safeHistory = history.length > 0 ? history : [0];
  const min = Math.min(...safeHistory) - 5;
  const max = Math.max(...safeHistory) + 5;
  const valueRange = max - min || 1;

  const pointCount = safeHistory.length;
  const pts = safeHistory.map((v, i) => {
    const x = pointCount === 1 ? W / 2 : PAD + (i / (pointCount - 1)) * (W - PAD * 2);
    const y = PAD + (1 - (v - min) / valueRange) * (H - PAD * 2);
    return [x, y] as [number, number];
  });

  const d = pts.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(' ');
  const area =
    d + ` L${pts[pts.length - 1][0]},${H - PAD} L${PAD},${H - PAD} Z`;

  const gridLines = [0.25, 0.5, 0.75];
  const labels = LABELS_BY_RANGE[chartRange];

  return (
    <svg viewBox={`0 0 ${W} ${H + 22}`} className="tt-chart" aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {gridLines.map((p) => (
        <line
          key={p}
          x1={PAD}
          x2={W - PAD}
          y1={PAD + p * (H - PAD * 2)}
          y2={PAD + p * (H - PAD * 2)}
          stroke="oklch(0.92 0.005 260)"
          strokeDasharray="2 4"
        />
      ))}
      <path d={area} fill={`url(#${gradId})`} />
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {pts.map(([x, y], i) => (
        <circle key={`pt-x${x.toFixed(0)}`} cx={x} cy={y} r={i === pts.length - 1 ? 3.5 : 0} fill={color} />
      ))}
      {pts.length > 0 && (
        <circle
          cx={pts[pts.length - 1][0]}
          cy={pts[pts.length - 1][1]}
          r="6"
          fill={color}
          opacity="0.18"
        />
      )}
      {labels.map((l, i) => (
        <text
          key={l}
          x={PAD + (i / (labels.length - 1)) * (W - PAD * 2)}
          y={H + 14}
          textAnchor="middle"
          fontSize="9"
          fontFamily="var(--font-jetbrains-mono), monospace"
          fill="oklch(0.55 0.01 260)"
          letterSpacing="0.04em"
        >
          {l}
        </text>
      ))}
    </svg>
  );
}
