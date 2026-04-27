export function sentimentColor(s: number): string {
  if (s <= -0.2) return 'oklch(0.55 0.18 25)';
  if (s < 0.2) return 'oklch(0.55 0.02 260)';
  return 'oklch(0.55 0.13 155)';
}

export function sentimentLabel(s: number): string {
  if (s <= -0.6) return 'Bardzo negatywny';
  if (s <= -0.2) return 'Negatywny';
  if (s < 0.2) return 'Neutralny';
  if (s < 0.6) return 'Pozytywny';
  return 'Bardzo pozytywny';
}

interface SentimentBarProps {
  value: number; // -1 .. 1
}

export function SentimentBar({ value }: SentimentBarProps) {
  const pct = ((value + 1) / 2) * 100;
  const c = sentimentColor(value);
  return (
    <div className="tt-sent-bar">
      <div className="tt-sent-track">
        <div className="tt-sent-mid" />
        <div
          className="tt-sent-fill"
          style={{
            left: `${Math.min(50, pct)}%`,
            width: `${Math.abs(pct - 50)}%`,
            background: c,
          }}
        />
        <div
          className="tt-sent-marker"
          style={{ left: `${pct}%`, background: c }}
        />
      </div>
      <span className="tt-sent-num tt-mono" style={{ color: c }}>
        {value > 0 ? '+' : ''}
        {value.toFixed(2)}
      </span>
    </div>
  );
}
