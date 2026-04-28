'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { getGraph, getCompanyTraces } from '@/lib/api';
import type { Article, Company, GraphResponse, HistoryRangeKey, ReasoningTrace } from '@/lib/data';
import { ScoreChart } from './score-chart';
import { TradingViewWidget } from './tradingview-widget';
import { ArticleRow } from './article-row';
import { CompanyGraph } from './company-graph';
import { getCompanyHistoryForRange, hasCompanyTradingView } from './main-panel-helpers';
import { riskColor, riskLabel } from './sidebar';
import { ToggleGroup, type ToggleOption } from './toggle-group';
import { TraceDrawer, traceHeadline, traceMethodBadge } from './trace-drawer';

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'przed chwilą';
  if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h temu`;
  return `${Math.floor(diff / 86400)} dni temu`;
}

type FilterKey = 'all' | 'neg' | 'pos' | 'high';
type MainPanelView = 'overview' | 'graph' | 'traces';
type TraceFilterKey = 'all' | 'EEM' | 'NSA' | 'Tarkov' | 'Market';

interface MainPanelProps {
  company: Company;
  articles: Article[];
  articlesLoading: boolean;
  articleError: string | null;
  onSelectCompany: (id: string) => void;
}

interface OverviewPanelProps {
  company: Company;
  articles: Article[];
  loading: boolean;
  error: string | null;
  accentColor: string;
}

function OverviewPanel({ company, articles, loading, error, accentColor }: OverviewPanelProps) {
  const [openId, setOpenId] = useState<string | null>(articles[0]?.id ?? null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [activeTab, setActiveTab] = useState<HistoryRangeKey>('12M');
  const [showTVChart, setShowTVChart] = useState(false);
  const tradingViewAvailable = hasCompanyTradingView(company);
  const displayedHistory = getCompanyHistoryForRange(company, activeTab);

  useEffect(() => {
    setOpenId(articles[0]?.id ?? null);
  }, [articles]);

  useEffect(() => {
    if (!tradingViewAvailable) {
      setShowTVChart(false);
    }
  }, [tradingViewAvailable]);

  const filtered = useMemo(() => {
    if (filter === 'neg') return articles.filter((article) => article.sentiment <= -0.2);
    if (filter === 'pos') return articles.filter((article) => article.sentiment >= 0.2);
    if (filter === 'high') return articles.filter((article) => Math.abs(article.impact) >= 3);
    return articles;
  }, [articles, filter]);

  const timeTabs: ToggleOption<HistoryRangeKey>[] = [
    { value: '12M', label: '12M' },
    { value: '6M', label: '6M' },
    { value: '3M', label: '3M' },
    { value: '30D', label: '30D' },
  ];
  const filterTabs: ToggleOption<FilterKey>[] = [
    { value: 'all', label: 'Wszystkie' },
    { value: 'neg', label: 'Negatywne' },
    { value: 'pos', label: 'Pozytywne' },
    { value: 'high', label: 'Wysoki wpływ' },
  ];

  return (
    <>
      <section className="tt-chart-section">
        <div className="tt-section-head">
          <div>
            <div className="tt-section-title">Historia scoringu</div>
            <div className="tt-section-sub">Zakres {activeTab} · dane z backendu</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: tradingViewAvailable ? 'pointer' : 'not-allowed', fontSize: 11, color: tradingViewAvailable ? 'oklch(0.55 0.01 260)' : 'oklch(0.7 0.01 260)', fontFamily: 'var(--font-jetbrains-mono), monospace', letterSpacing: '0.04em' }}>
              <input
                type="checkbox"
                checked={showTVChart}
                disabled={!tradingViewAvailable}
                onChange={(e) => setShowTVChart(e.target.checked)}
                style={{ accentColor: '#2962ff', cursor: tradingViewAvailable ? 'pointer' : 'not-allowed' }}
              />
              TRADINGVIEW
            </label>
            <ToggleGroup options={timeTabs} value={activeTab} onChange={setActiveTab} size="sm" />
          </div>
        </div>
        {!tradingViewAvailable && (
          <div className="tt-section-sub" style={{ marginBottom: 12 }}>
            Brak symbolu giełdowego w danych backendu
          </div>
        )}
        <div style={{ position: 'relative' }}>
          <ScoreChart history={displayedHistory} color={accentColor} range={activeTab} />
          {showTVChart && company.tradingViewSymbol && <TradingViewWidget symbol={company.tradingViewSymbol} />}
        </div>
      </section>

      <section className="tt-articles">
        <div className="tt-section-head">
          <div>
            <div className="tt-section-title">Publikacje medialne</div>
            <div className="tt-section-sub">
              Algorytm sentymentu · {filtered.length} z {articles.length}
            </div>
          </div>
          <ToggleGroup options={filterTabs} value={filter} onChange={setFilter} size="sm" />
        </div>

        <div className="tt-art-table-head">
          <div />
          <div>NAGŁÓWEK</div>
          <div>ŹRÓDŁO</div>
          <div>DATA</div>
          <div>SENTYMENT</div>
          <div>WPŁYW</div>
        </div>

        <div className="tt-art-list">
          {loading && (
            <div className="tt-empty" style={{ padding: 40 }}>
              Ładowanie publikacji dla {company.short}…
            </div>
          )}
          {!loading && error && (
            <div className="tt-empty" style={{ padding: 40 }}>
              Nie udało się pobrać publikacji: {error}
            </div>
          )}
          {!loading && !error && filtered.map((article, idx) => (
            <ArticleRow
              key={article.id}
              article={article}
              expanded={openId === article.id}
              onToggle={() => setOpenId(openId === article.id ? null : article.id)}
              idx={idx}
            />
          ))}
          {!loading && !error && filtered.length === 0 && (
            <div className="tt-empty" style={{ padding: 40 }}>
              Brak artykułów spełniających kryteria.
            </div>
          )}
        </div>
      </section>
    </>
  );
}

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

function formatTraceTimestamp(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()} · ${hh}:${min}`;
}

interface TracesPanelProps {
  company: Company;
}

function TracesPanel({ company }: TracesPanelProps) {
  const [traces, setTraces] = useState<ReasoningTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TraceFilterKey>('all');
  const [drawerTrace, setDrawerTrace] = useState<ReasoningTrace | null>(null);
  const [lastCompanyId, setLastCompanyId] = useState(company.id);

  if (lastCompanyId !== company.id) {
    setLastCompanyId(company.id);
    setLoading(true);
    setError(null);
    setTraces([]);
  }

  useEffect(() => {
    let cancelled = false;
    getCompanyTraces(company.id)
      .then((data) => {
        if (!cancelled) {
          data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          setTraces(data);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Nieznany błąd');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [company.id]);

  const filtered = useMemo(() => {
    if (filter === 'all') return traces;
    return traces.filter((t) => t.classifier_name === filter);
  }, [traces, filter]);

  const filterTabs: ToggleOption<TraceFilterKey>[] = [
    { value: 'all', label: 'Wszystkie' },
    { value: 'EEM', label: 'EEM' },
    { value: 'NSA', label: 'NSA' },
    { value: 'Tarkov', label: 'Tarkov' },
    { value: 'Market', label: 'Market' },
  ];

  return (
    <section className="tt-trace-tab">
      <div className="tt-section-head">
        <div>
          <div className="tt-section-title">Ścieżki decyzyjne</div>
          <div className="tt-section-sub">
            Trace klasyfikatorów dla {company.short} · {filtered.length} z {traces.length}
          </div>
        </div>
        <ToggleGroup options={filterTabs} value={filter} onChange={setFilter} size="sm" />
      </div>

      {loading && (
        <div className="tt-empty" style={{ padding: 40 }}>
          Ładowanie trace dla {company.short}…
        </div>
      )}

      {!loading && error && (
        <div className="tt-trace-error" style={{ padding: 40 }}>
          <div className="tt-trace-error-msg">Nie udało się pobrać trace</div>
          <div className="tt-trace-error-detail">{error}</div>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="tt-empty" style={{ padding: 40 }}>
          Brak danych trace {filter !== 'all' ? `dla klasyfikatora ${filter}` : ''}.
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="tt-trace-table">
          <div className="tt-trace-table-head">
            <div>KLASYFIKATOR</div>
            <div>OPIS</div>
            <div>METODA</div>
            <div>DATA</div>
          </div>
          {filtered.map((trace) => {
            const color = CLASSIFIER_COLORS[trace.classifier_name] ?? 'var(--tt-fg-mute)';
            const headline = traceHeadline(trace);
            const method = traceMethodBadge(trace);
            return (
              <button
                key={`${trace.classifier_name}-${trace.entity_id}-${trace.created_at}`}
                type="button"
                className="tt-trace-table-row"
                onClick={() => setDrawerTrace(trace)}
              >
                <div>
                  <span className="tt-trace-badge" style={{ background: color }}>
                    {trace.classifier_name}
                  </span>
                </div>
                <div className="tt-trace-table-cell tt-trace-table-desc">{headline}</div>
                <div className="tt-trace-table-cell">
                  {method && <span className="tt-trace-method">{method}</span>}
                  {!method && <span className="tt-trace-type-pill">{trace.entity_type}</span>}
                </div>
                <div className="tt-trace-table-cell tt-mono">
                  {formatTraceTimestamp(trace.created_at)}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {drawerTrace && (
        <TraceDrawer
          open={!!drawerTrace}
          onClose={() => setDrawerTrace(null)}
          initialTrace={drawerTrace}
          title={`Ścieżka decyzyjna — ${CLASSIFIER_LABELS[drawerTrace.classifier_name] ?? drawerTrace.classifier_name}`}
        />
      )}
    </section>
  );
}

interface GraphPanelProps {
  company: Company;
  graph: GraphResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectCompany: (id: string) => void;
}

function GraphPanel({ company, graph, loading, error, onRetry, onSelectCompany }: GraphPanelProps) {
  if (loading && !graph) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Ładowanie mapy powiązań…</div>
      </div>
    );
  }

  if (error && !graph) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-graph-feedback">
          <div className="tt-graph-feedback-title">Nie udało się pobrać mapy powiązań</div>
          <div className="tt-graph-feedback-sub">{error}</div>
          <button type="button" className="tt-graph-clear" onClick={onRetry}>
            Spróbuj ponownie
          </button>
        </div>
      </div>
    );
  }

  if (!graph) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Brak danych grafu dla {company.short}.</div>
      </div>
    );
  }

  return <CompanyGraph company={company} graph={graph} onSelectCompany={onSelectCompany} />;
}

export function MainPanel({
  company,
  articles,
  articlesLoading,
  articleError,
  onSelectCompany,
}: MainPanelProps) {
  const [activeView, setActiveView] = useState<MainPanelView>('overview');
  const [graphCache, setGraphCache] = useState<Record<string, GraphResponse>>({});
  const [graphLoadingById, setGraphLoadingById] = useState<Record<string, boolean>>({});
  const [graphErrorById, setGraphErrorById] = useState<Record<string, string | null>>({});
  const accentColor = riskColor(company.risk);

  const loadGraph = useCallback(async (companyId: string, force = false) => {
    if (!force && graphCache[companyId]) {
      return;
    }

    setGraphLoadingById((current) => ({ ...current, [companyId]: true }));
    setGraphErrorById((current) => ({ ...current, [companyId]: null }));

    try {
      const graph = await getGraph(companyId);
      setGraphCache((current) => ({ ...current, [companyId]: graph }));
    } catch (nextError) {
      setGraphErrorById((current) => ({
        ...current,
        [companyId]: nextError instanceof Error ? nextError.message : 'Unknown error',
      }));
    } finally {
      setGraphLoadingById((current) => ({ ...current, [companyId]: false }));
    }
  }, [graphCache]);

  useEffect(() => {
    if (activeView !== 'graph') {
      return;
    }

    void loadGraph(company.id);
  }, [activeView, company.id, loadGraph]);

  const graph = graphCache[company.id] ?? null;
  const graphLoading = graphLoadingById[company.id] ?? false;
  const graphError = graphErrorById[company.id] ?? null;

  return (
    <main className="tt-main">
      <header className="tt-mhead">
        <div className="tt-mhead-left">
          <div className="tt-bread tt-mono">
            <span>RECORDS</span>
            <span className="tt-bread-sep">/</span>
            <span>{company.sector.toUpperCase()}</span>
            <span className="tt-bread-sep">/</span>
            <span className="tt-bread-cur">{company.short.toUpperCase()}</span>
          </div>
          <h1 className="tt-company-name">{company.name}</h1>
          <div className="tt-meta-row">
            <div className="tt-meta-item">
              <span className="tt-meta-label">NIP</span>
              <span className="tt-mono">{company.nip}</span>
            </div>
            <div className="tt-meta-item">
              <span className="tt-meta-label">Sektor</span>
              <span>{company.sector}</span>
            </div>
            <div className="tt-meta-item">
              <span className="tt-meta-label">Artykuły (90 dni)</span>
              <span className="tt-mono">{company.articles}</span>
            </div>
            <div className="tt-meta-item">
              <span className="tt-meta-label">Ostatnia aktualizacja</span>
              <span className="tt-mono">{relativeTime(company.lastUpdate)}</span>
            </div>
          </div>
        </div>

        <div className="tt-mhead-right">
          <div className="tt-score-card">
            <div className="tt-score-label">Trust score</div>
            <div className="tt-score-value" style={{ color: accentColor }}>
              {company.score}
              <span className="tt-score-of">/100</span>
            </div>
            <div
              className={
                'tt-score-trend' +
                (company.trend < 0 ? ' is-neg' : company.trend > 0 ? ' is-pos' : '')
              }
            >
              {company.trend > 0 ? '↑' : company.trend < 0 ? '↓' : '·'} {Math.abs(company.trend)} pkt · 30 dni
            </div>
          </div>
          <div className={'tt-risk-pill tt-risk-' + company.risk}>
            <span className="tt-risk-dot" style={{ background: accentColor }} />
            Ryzyko: {riskLabel(company.risk)}
          </div>
        </div>
      </header>

      <section className="tt-main-switcher">
        <ToggleGroup
          options={[
            { value: 'overview' as MainPanelView, label: 'Overview' },
            { value: 'graph' as MainPanelView, label: 'Graph' },
            { value: 'traces' as MainPanelView, label: 'Traces' },
          ]}
          value={activeView}
          onChange={setActiveView}
          size="lg"
          role="tablist"
          ariaLabel="Przełącznik widoku panelu firmy"
        />
      </section>

      {activeView === 'overview' && (
        <OverviewPanel
          key={company.id}
          company={company}
          articles={articles}
          loading={articlesLoading}
          error={articleError}
          accentColor={accentColor}
        />
      )}
      {activeView === 'graph' && (
        <section className="tt-graph-view">
          <div className="tt-section-head">
            <div>
              <div className="tt-section-title">Mapa powiązań</div>
              <div className="tt-section-sub">
                Spółki, osoby i zdarzenia renderowane bezpośrednio z grafu backendowego.
              </div>
            </div>
          </div>
          <GraphPanel
            company={company}
            graph={graph}
            loading={graphLoading}
            error={graphError}
            onRetry={() => void loadGraph(company.id, true)}
            onSelectCompany={onSelectCompany}
          />
        </section>
      )}
      {activeView === 'traces' && (
        <TracesPanel key={company.id} company={company} />
      )}
    </main>
  );
}
