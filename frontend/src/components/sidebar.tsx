'use client';

import { useState, useMemo } from 'react';
import type { Company, Risk } from '@/lib/data';
import { AnalysisLauncher } from './analysis-launcher';
import { hasPendingScore } from './main-panel-helpers';
import { Sparkline } from './sparkline';
import { ToggleGroup, type ToggleOption } from './toggle-group';

function riskColor(risk: Risk): string {
  if (risk === 'high') return 'oklch(0.55 0.18 25)';
  if (risk === 'medium') return 'oklch(0.65 0.13 70)';
  return 'oklch(0.55 0.13 155)';
}

function riskLabel(risk: Risk): string {
  if (risk === 'high') return 'High';
  if (risk === 'medium') return 'Med';
  return 'Low';
}

export { riskColor, riskLabel };

const PENDING_COLOR = 'oklch(0.58 0.03 255)';

type SortKey = 'risk' | 'name' | 'recent';

interface SidebarProps {
  companies: Company[];
  selectedId: string;
  onSelect: (id: string) => void;
  analysisQuery: string;
  onAnalysisQueryChange: (value: string) => void;
  onStartAnalysis: () => void | Promise<void>;
  analysisBusy: boolean;
  analysisStatus: string | null;
  analysisError: string | null;
}

export function Sidebar({
  companies,
  selectedId,
  onSelect,
  analysisQuery,
  onAnalysisQueryChange,
  onStartAnalysis,
  analysisBusy,
  analysisStatus,
  analysisError,
}: SidebarProps) {
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('risk');

  const filtered = useMemo(() => {
    let list = companies;
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.short.toLowerCase().includes(q) ||
          c.nip.includes(q) ||
          c.sector.toLowerCase().includes(q)
      );
    }
    const sorted = [...list];
    if (sortBy === 'risk') {
      sorted.sort((a, b) => {
        const aPending = hasPendingScore(a);
        const bPending = hasPendingScore(b);

        if (aPending !== bPending) {
          return aPending ? 1 : -1;
        }

        return a.score - b.score;
      });
    }
    else if (sortBy === 'name') sorted.sort((a, b) => a.short.localeCompare(b.short));
    else sorted.sort((a, b) => b.lastUpdate.localeCompare(a.lastUpdate));
    return sorted;
  }, [companies, query, sortBy]);

  const counts = useMemo(
    () => ({
      pending: companies.filter((c) => hasPendingScore(c)).length,
      high: companies.filter((c) => c.risk === 'high').length,
      medium: companies.filter((c) => c.risk === 'medium' && !hasPendingScore(c)).length,
      low: companies.filter((c) => c.risk === 'low').length,
    }),
    [companies]
  );

  const sortOptions: ToggleOption<SortKey>[] = [
    { value: 'risk', label: 'Ryzyko' },
    { value: 'name', label: 'Nazwa' },
    { value: 'recent', label: 'Ostatnie' },
  ];

  return (
    <aside className="tt-sidebar">
      <div className="tt-sidebar-head">
        <AnalysisLauncher
          query={analysisQuery}
          onQueryChange={onAnalysisQueryChange}
          onSubmit={onStartAnalysis}
          busy={analysisBusy}
          status={analysisStatus}
          error={analysisError}
          compact
        />

        <div className="tt-search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            placeholder="Szukaj firmy, NIP, sektor…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            spellCheck={false}
            aria-label="Szukaj firmy"
          />
          {query && (
            <button
              type="button"
              className="tt-clear"
              onClick={() => setQuery('')}
              aria-label="Wyczyść"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        <div className="tt-summary">
          {([
            { key: 'pending', label: 'w toku', color: PENDING_COLOR },
            { key: 'high', label: 'wysokie', color: riskColor('high') },
            { key: 'medium', label: 'średnie', color: riskColor('medium') },
            { key: 'low', label: 'niskie', color: riskColor('low') },
          ] as const).map((r) => (
            <div key={r.key} className="tt-sum-item">
              <span className="tt-dot" style={{ background: r.color }} />
              <span className="tt-sum-num">{counts[r.key]}</span>
              <span className="tt-sum-label">{r.label}</span>
            </div>
          ))}
        </div>

        <ToggleGroup options={sortOptions} value={sortBy} onChange={setSortBy} size="sm" />
      </div>

      <div className="tt-list">
        {filtered.length === 0 && (
          <div className="tt-empty">
            {query ? `Brak wyników dla „${query}”` : 'Baza jest pusta. Uruchom analizę powyżej.'}
          </div>
        )}
        {filtered.map((c, idx) => {
          const isActive = c.id === selectedId;
          const isPending = hasPendingScore(c);
          const rowColor = isPending ? PENDING_COLOR : riskColor(c.risk);

          return (
            <button
              key={c.id}
              type="button"
              className={'tt-row' + (isActive ? ' is-active' : '')}
              onClick={() => onSelect(c.id)}
              style={{ animationDelay: `${idx * 14}ms` }}
            >
              <div className="tt-row-bar" style={{ background: rowColor }} />
              <div className="tt-row-main">
                <div className="tt-row-top">
                  <span className="tt-row-name">{c.short}</span>
                  {isPending ? (
                    <span className="tt-row-pending-pill">scoring…</span>
                  ) : (
                    <span className="tt-row-score" style={{ color: rowColor }}>
                      {c.score}
                    </span>
                  )}
                </div>
                <div className="tt-row-bot">
                  <span className="tt-row-sector">{c.sector}</span>
                  {isPending ? (
                    <span className="tt-row-trend is-pending">Czeka na wynik</span>
                  ) : (
                    <span
                      className={
                        'tt-row-trend' +
                        (c.trend < 0 ? ' is-neg' : c.trend > 0 ? ' is-pos' : '')
                      }
                    >
                      {c.trend > 0 ? '↑' : c.trend < 0 ? '↓' : '·'} {Math.abs(c.trend)}
                    </span>
                  )}
                </div>
              </div>
              <div className="tt-row-spark">
                {isPending ? (
                  <div className="tt-row-spark-placeholder" aria-hidden="true" />
                ) : (
                  <Sparkline data={c.history} color={rowColor} />
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="tt-sidebar-foot">
        <div className="tt-foot-row">
          <span>Ostatnia synchronizacja</span>
          <span className="tt-mono">14:32:08</span>
        </div>
        <div className="tt-foot-row">
          <span>Źródła aktywne</span>
          <span className="tt-mono">38 / 41</span>
        </div>
      </div>
    </aside>
  );
}
