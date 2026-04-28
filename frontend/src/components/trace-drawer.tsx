'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReasoningTrace } from '@/lib/data';
import { getTraces, getTracesByCorrelation } from '@/lib/api';

const CLASSIFIER_COLORS: Record<string, string> = {
  EEM: 'oklch(0.65 0.13 70)',
  NSA: 'oklch(0.55 0.18 25)',
  Tarkov: 'oklch(0.55 0.16 250)',
  Market: 'oklch(0.55 0.13 155)',
};

const CLASSIFIER_LABELS: Record<string, string> = {
  EEM: 'Ocena zdarzeń',
  NSA: 'Scoring osób',
  Tarkov: 'Ekstrakcja zdarzeń',
  Market: 'Dane rynkowe',
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()} · ${hh}:${min}`;
}

function isUrl(value: string): boolean {
  return /^https?:\/\//.test(value);
}

function formatKey(key: string): string {
  return key.replace(/_/g, ' ');
}

export function traceHeadline(trace: ReasoningTrace): string {
  const td = trace.trace_data as Record<string, unknown>;
  switch (trace.classifier_name) {
    case 'EEM': {
      const sc = td.sentiment_calculation as Record<string, unknown> | undefined;
      const ks = td.keyword_extraction as Record<string, unknown> | undefined;
      const eventType = (sc?.event_type as string) || '';
      const kws = (ks?.top_6_keywords as string[]) || (ks?.extracted_keywords as string[]) || [];
      const sentiment = sc?.final_sentiment as number | undefined;
      const parts: string[] = [];
      if (eventType) parts.push(eventType);
      if (sentiment !== undefined) parts.push(`sentyment ${sentiment > 0 ? '+' : ''}${sentiment.toFixed(2)}`);
      if (kws.length) parts.push(kws.slice(0, 3).join(', '));
      return parts.join(' · ') || 'Analiza zdarzenia';
    }
    case 'NSA': {
      const pc = td.person_context as Record<string, unknown> | undefined;
      const ag = td.aggregation_logic as Record<string, unknown> | undefined;
      const name = (pc?.person_name as string) || '';
      const role = (pc?.role as string) || '';
      const score = ag?.clamped_score as number | undefined;
      const parts: string[] = [];
      if (name) parts.push(name);
      if (role) parts.push(role);
      if (score !== undefined) parts.push(`score ${score.toFixed(1)}`);
      return parts.join(' · ') || 'Scoring osoby';
    }
    case 'Tarkov': {
      const km = td.keyword_matching as Record<string, unknown> | undefined;
      const tg = td.title_generation as Record<string, unknown> | undefined;
      const sr = td.source_reference as Record<string, unknown> | undefined;
      const eventType = (km?.event_type as string) || '';
      const title = (tg?.generated_title as string) || (tg?.article_title as string) || '';
      const source = (sr?.source_title as string) || '';
      const parts: string[] = [];
      if (eventType) parts.push(eventType);
      if (title) parts.push(title.length > 60 ? title.slice(0, 57) + '…' : title);
      else if (source) parts.push(source.length > 60 ? source.slice(0, 57) + '…' : source);
      return parts.join(' · ') || 'Ekstrakcja zdarzenia';
    }
    case 'Market': {
      const ts = td.ticker_search as Record<string, unknown> | undefined;
      const fr = td.fetch_results as Record<string, unknown> | undefined;
      const firm = (ts?.firm_name as string) || '';
      const success = fr?.successful_fetches as number | undefined;
      const parts: string[] = [];
      if (firm) parts.push(firm);
      if (success !== undefined) parts.push(`${success} serii danych`);
      return parts.join(' · ') || 'Dane rynkowe';
    }
    default:
      return trace.entity_type;
  }
}

export function traceMethodBadge(trace: ReasoningTrace): string | null {
  const td = trace.trace_data as Record<string, unknown>;
  if (trace.classifier_name === 'EEM') {
    return (td.model_used as string) || null;
  }
  if (trace.classifier_name === 'Tarkov') {
    return (td.extraction_method as string)?.replace('_', ' ') || null;
  }
  return null;
}

function TraceValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) {
    return <span className="tt-trace-val tt-trace-null">—</span>;
  }

  if (typeof value === 'boolean') {
    return (
      <span className={`tt-trace-val tt-trace-bool ${value ? 'is-true' : 'is-false'}`}>
        {value ? '✓' : '✗'}
      </span>
    );
  }

  if (typeof value === 'number') {
    const display = Number.isInteger(value) ? String(value) : value.toFixed(2);
    return <span className="tt-trace-val tt-trace-num">{display}</span>;
  }

  if (typeof value === 'string') {
    if (isUrl(value)) {
      return (
        <a href={value} target="_blank" rel="noreferrer" className="tt-trace-val tt-trace-url">
          {value}
        </a>
      );
    }
    return <span className="tt-trace-val">{value}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="tt-trace-val tt-trace-null">[]</span>;

    const allPrimitive = value.every((v) => typeof v !== 'object' || v === null);
    if (allPrimitive && value.length < 10) {
      return (
        <ul className="tt-trace-list">
          {value.map((item, i) => (
            <li key={i}>
              <TraceValue value={item} depth={depth + 1} />
            </li>
          ))}
        </ul>
      );
    }

    return (
      <CollapsibleSection label={`${value.length} elementów`} defaultOpen={depth < 1 && value.length < 6}>
        <ul className="tt-trace-list">
          {value.map((item, i) => (
            <li key={i}>
              <TraceValue value={item} depth={depth + 1} />
            </li>
          ))}
        </ul>
      </CollapsibleSection>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="tt-trace-val tt-trace-null">{'{}'}</span>;

    return (
      <div className="tt-trace-tree-nested">
        {entries.map(([key, val]) => (
          <div key={key} className="tt-trace-row">
            <span className="tt-trace-key">{formatKey(key)}</span>
            <TraceValue value={val} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }

  return <span className="tt-trace-val">{String(value)}</span>;
}

function CollapsibleSection({
  label,
  defaultOpen,
  children,
}: {
  label: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="tt-trace-collapsible">
      <button
        type="button"
        className="tt-trace-collapse-btn"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          aria-hidden="true"
          style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}
        >
          <path d="m9 6 6 6-6 6" />
        </svg>
        {label}
      </button>
      {open && children}
    </div>
  );
}

function TraceCard({
  trace,
  defaultOpen,
}: {
  trace: ReasoningTrace;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const color = CLASSIFIER_COLORS[trace.classifier_name] ?? 'var(--tt-fg-mute)';
  const headline = traceHeadline(trace);
  const method = traceMethodBadge(trace);

  return (
    <div className={'tt-trace-card' + (open ? ' is-open' : '')}>
      <button type="button" className="tt-trace-card-head" onClick={() => setOpen(!open)}>
        <div className="tt-trace-card-left">
          <span className="tt-trace-badge" style={{ background: color }}>
            {trace.classifier_name}
          </span>
          <span className="tt-trace-headline">{headline}</span>
          {method && <span className="tt-trace-method">{method}</span>}
        </div>
        <div className="tt-trace-card-right">
          <span className="tt-trace-time tt-mono">{formatTimestamp(trace.created_at)}</span>
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            aria-hidden="true"
            className="tt-trace-card-chev"
          >
            <path d="m9 6 6 6-6 6" />
          </svg>
        </div>
      </button>
      {open && (
        <div className="tt-trace-card-body">
          <div className="tt-trace-card-meta">
            <span className="tt-trace-meta-label">Klasyfikator</span>
            <span>{CLASSIFIER_LABELS[trace.classifier_name] ?? trace.classifier_name}</span>
          </div>
          <div className="tt-trace-card-meta">
            <span className="tt-trace-meta-label">Typ encji</span>
            <span>{trace.entity_type}</span>
          </div>
          <div className="tt-trace-tree">
            {Object.entries(trace.trace_data).map(([key, val]) => (
              <div key={key} className="tt-trace-section">
                <div className="tt-trace-section-title">{formatKey(key)}</div>
                <TraceValue value={val} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  classifier?: string;
  entityId?: string;
  correlationId?: string;
  title?: string;
  initialTrace?: ReasoningTrace;
}

export function TraceDrawer({
  open,
  onClose,
  classifier,
  entityId,
  correlationId,
  title,
  initialTrace,
}: TraceDrawerProps) {
  const hasInitial = !!initialTrace;
  const [fetched, setFetched] = useState<ReasoningTrace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);
  const drawerRef = useRef<HTMLDivElement>(null);

  const traces = hasInitial ? [initialTrace] : fetched;

  const retryFetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    if (!open || hasInitial) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    async function run() {
      try {
        let data: ReasoningTrace[];
        if (correlationId) {
          data = await getTracesByCorrelation(correlationId);
        } else if (classifier && entityId) {
          data = await getTraces(classifier, entityId);
        } else {
          data = [];
        }
        if (!cancelled) {
          data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          setFetched(data);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Nieznany błąd');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => { cancelled = true; };
  }, [open, classifier, entityId, correlationId, hasInitial, fetchKey]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open && drawerRef.current) {
      drawerRef.current.focus();
    }
  }, [open]);

  if (!open) return null;

  const displayTitle =
    title ??
    (correlationId
      ? 'Ścieżka decyzyjna — korelacja'
      : `Ścieżka decyzyjna — ${classifier ?? ''}`);

  return (
    <>
      <div className="tt-trace-backdrop" onClick={onClose} aria-hidden="true" />
      <aside
        ref={drawerRef}
        className="tt-trace-drawer"
        role="dialog"
        aria-label={displayTitle}
        tabIndex={-1}
      >
        <header className="tt-trace-drawer-head">
          <div>
            <div className="tt-trace-drawer-title">{displayTitle}</div>
            <div className="tt-trace-drawer-sub">
              {traces.length} {traces.length === 1 ? 'wynik' : 'wyników'}
            </div>
          </div>
          <button
            type="button"
            className="tt-trace-drawer-close"
            onClick={onClose}
            aria-label="Zamknij"
          >
            ×
          </button>
        </header>

        <div className="tt-trace-drawer-body">
          {loading && (
            <div className="tt-trace-skeleton">
              <div className="tt-trace-skeleton-bar" />
              <div className="tt-trace-skeleton-bar" style={{ width: '70%' }} />
              <div className="tt-trace-skeleton-bar" style={{ width: '85%' }} />
              <div className="tt-trace-skeleton-bar" style={{ width: '60%' }} />
            </div>
          )}

          {!loading && error && (
            <div className="tt-trace-error">
              <div className="tt-trace-error-msg">Nie udało się pobrać danych trace</div>
              <div className="tt-trace-error-detail">{error}</div>
              <button type="button" className="tt-btn-ghost" onClick={retryFetch}>
                Spróbuj ponownie
              </button>
            </div>
          )}

          {!loading && !error && traces.length === 0 && (
            <div className="tt-trace-empty">
              <div className="tt-trace-empty-title">Brak danych trace</div>
              <div className="tt-trace-empty-desc">
                Pipeline mógł jeszcze nie przetworzyć tej encji. Dane pojawią się po następnym uruchomieniu klasyfikatora.
              </div>
            </div>
          )}

          {!loading &&
            !error &&
            traces.map((trace, idx) => (
              <TraceCard
                key={`${trace.classifier_name}-${trace.entity_id}-${trace.created_at}`}
                trace={trace}
                defaultOpen={idx === 0}
              />
            ))}
        </div>
      </aside>
    </>
  );
}
