'use client';

import { useCallback, useMemo, useState } from 'react';
import type { Article, Company, CompanyRelation } from '@/lib/data';
import { ScoreChart } from './score-chart';
import { TradingViewWidget } from './tradingview-widget';
import { ArticleRow } from './article-row';
import { CompanyGraph } from './company-graph';
import { riskColor, riskLabel } from './sidebar';
import { ToggleGroup, type ToggleOption } from './toggle-group';

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'przed chwilą';
  if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h temu`;
  return `${Math.floor(diff / 86400)} dni temu`;
}

type FilterKey = 'all' | 'neg' | 'pos' | 'high';
type MainPanelView = 'overview' | 'graph';

interface MainPanelProps {
  company: Company;
  companies: Company[];
  articles: Article[];
  relations: CompanyRelation[];
  onSelectCompany: (id: string) => void;
}

interface OverviewPanelProps {
  company: Company;
  articles: Article[];
  accentColor: string;
}

function OverviewPanel({ company, articles, accentColor }: OverviewPanelProps) {
  const [openId, setOpenId] = useState<string | null>(articles[0]?.id ?? null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [activeTab, setActiveTab] = useState('12M');
  const [showTVChart, setShowTVChart] = useState(false);

  const filtered = useMemo(() => {
    if (filter === 'neg') return articles.filter((article) => article.sentiment <= -0.2);
    if (filter === 'pos') return articles.filter((article) => article.sentiment >= 0.2);
    if (filter === 'high') return articles.filter((article) => Math.abs(article.impact) >= 3);
    return articles;
  }, [articles, filter]);

  const timeTabs: ToggleOption[] = [
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
            <div className="tt-section-sub">Ostatnich 12 miesięcy · agregat dzienny</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 11, color: 'oklch(0.55 0.01 260)', fontFamily: 'var(--font-jetbrains-mono), monospace', letterSpacing: '0.04em' }}>
              <input
                type="checkbox"
                checked={showTVChart}
                onChange={(e) => setShowTVChart(e.target.checked)}
                style={{ accentColor: '#2962ff', cursor: 'pointer' }}
              />
              TRADINGVIEW
            </label>
            <ToggleGroup options={timeTabs} value={activeTab} onChange={setActiveTab} size="sm" />
          </div>
        </div>
        <div style={{ position: 'relative' }}>
          <ScoreChart history={company.history} color={accentColor} />
          {showTVChart && <TradingViewWidget symbol="GPW:CDR" />}
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
          {filtered.map((article, idx) => (
            <ArticleRow
              key={article.id}
              article={article}
              expanded={openId === article.id}
              onToggle={() => setOpenId(openId === article.id ? null : article.id)}
              idx={idx}
            />
          ))}
          {filtered.length === 0 && (
            <div className="tt-empty" style={{ padding: 40 }}>
              Brak artykułów spełniających kryteria.
            </div>
          )}
        </div>
      </section>
    </>
  );
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars -- onSelectCompany kept for API parity; graph uses local refocus
export function MainPanel({ company, companies, articles, relations, onSelectCompany }: MainPanelProps) {
  const [activeView, setActiveView] = useState<MainPanelView>('overview');
  const accentColor = riskColor(company.risk);

  // Local graph center: stores { baseId, centerId } so we can detect when the
  // global company changes and auto-reset without an effect or ref.
  const [graphFocus, setGraphFocus] = useState<{ baseId: string; centerId: string }>({
    baseId: company.id,
    centerId: company.id,
  });

  // Derive the actual center. If the global company changed since we last set
  // the focus, fall back to the new company (reset on external selection change).
  const graphCenterId = graphFocus.baseId === company.id
    ? graphFocus.centerId
    : company.id;

  const graphCenterCompany = useMemo(
    () => companies.find((c) => c.id === graphCenterId) ?? company,
    [companies, graphCenterId, company],
  );

  const handleGraphNodeClick = useCallback((nodeId: string) => {
    setGraphFocus({ baseId: company.id, centerId: nodeId });
  }, [company.id]);

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
          ]}
          value={activeView}
          onChange={setActiveView}
          size="lg"
          role="tablist"
          ariaLabel="Przełącznik widoku panelu firmy"
        />
      </section>

      {activeView === 'overview' ? (
        <OverviewPanel
          key={company.id}
          company={company}
          articles={articles}
          accentColor={accentColor}
        />
      ) : (
        <section className="tt-graph-view">
          <div className="tt-section-head">
            <div>
              <div className="tt-section-title">Mapa relacji firmowych</div>
              <div className="tt-section-sub">
                Kliknij węzeł, aby przenieść na niego fokus grafu.
              </div>
            </div>
          </div>
          <CompanyGraph
            company={graphCenterCompany}
            companies={companies}
            relations={relations}
            onSelectCompany={handleGraphNodeClick}
          />
        </section>
      )}
    </main>
  );
}
