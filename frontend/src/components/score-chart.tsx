'use client';

import { useId } from 'react';

import type { HistoryRangeKey } from '@/lib/data';

interface ScoreChartProps {
  history: number[];
  color: string;
  range: HistoryRangeKey;
}

function labelsForRange(range: HistoryRangeKey): string[] {
  switch (range) {
    case '30D':
      return ['30D temu', '20D', '10D', 'dziś'];
    case '3M':
      return ['3M temu', '2M', '1M', 'dziś'];
    case '6M':
      return ['6M temu', '4M', '2M', 'dziś'];
    case '12M':
    default:
      return ['12M temu', '9M', '6M', '3M', 'dziś'];
  }
}

export function ScoreChart({ history, color, range: timeRange }: ScoreChartProps) {
  const safeHistory = history.length > 0 ? history : [0];
  const gradId = useId();
  const W = 640;
  const H = 120;
  const PAD = 16;
  const min = Math.min(...safeHistory) - 5;
  const max = Math.max(...safeHistory) + 5;
  const valueRange = max - min || 1;
  const pointCount = Math.max(safeHistory.length - 1, 1);

  const pts = safeHistory.map((v, i) => {
    const x = PAD + (i / pointCount) * (W - PAD * 2);
    const y = PAD + (1 - (v - min) / valueRange) * (H - PAD * 2);
    return [x, y] as [number, number];
  });

  const d = pts.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(' ');
  const area =
    d + ` L${pts[pts.length - 1][0]},${H - PAD} L${PAD},${H - PAD} Z`;

  const gridLines = [0.25, 0.5, 0.75];
  const labels = labelsForRange(timeRange);

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
