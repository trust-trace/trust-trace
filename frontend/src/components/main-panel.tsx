'use client';

import { useState, useMemo, useEffect } from 'react';
import type { Company, Article } from '@/lib/data';
import { ScoreChart } from './score-chart';
import { ArticleRow } from './article-row';
import { riskColor, riskLabel } from './sidebar';

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'przed chwilą';
  if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h temu`;
  return `${Math.floor(diff / 86400)} dni temu`;
}

type FilterKey = 'all' | 'neg' | 'pos' | 'high';

interface MainPanelProps {
  company: Company;
  articles: Article[];
}

export function MainPanel({ company, articles }: MainPanelProps) {
  const [openId, setOpenId] = useState<string | null>(articles[0]?.id ?? null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [activeTab, setActiveTab] = useState('12M');

  // Reset open article on company change
  useEffect(() => {
    setOpenId(articles[0]?.id ?? null);
    setFilter('all');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [articles]);

  const filtered = useMemo(() => {
    if (filter === 'neg') return articles.filter((a) => a.sentiment <= -0.2);
    if (filter === 'pos') return articles.filter((a) => a.sentiment >= 0.2);
    if (filter === 'high') return articles.filter((a) => Math.abs(a.impact) >= 3);
    return articles;
  }, [articles, filter]);

  const rc = riskColor(company.risk);
  const timeTabs = ['12M', '6M', '3M', '30D'];
  const filterTabs: [FilterKey, string][] = [
    ['all', 'Wszystkie'],
    ['neg', 'Negatywne'],
    ['pos', 'Pozytywne'],
    ['high', 'Wysoki wpływ'],
  ];

  return (
    <main className="tt-main" key={company.id}>
      {/* Company header */}
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
            <div className="tt-score-value" style={{ color: rc }}>
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
            <span className="tt-risk-dot" style={{ background: rc }} />
            Ryzyko: {riskLabel(company.risk)}
          </div>
        </div>
      </header>

      {/* Score history chart */}
      <section className="tt-chart-section">
        <div className="tt-section-head">
          <div>
            <div className="tt-section-title">Historia scoringu</div>
            <div className="tt-section-sub">Ostatnich 12 miesięcy · agregat dzienny</div>
          </div>
          <div className="tt-chart-tabs">
            {timeTabs.map((t) => (
              <button
                key={t}
                type="button"
                className={'tt-tab' + (activeTab === t ? ' is-active' : '')}
                onClick={() => setActiveTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <ScoreChart history={company.history} color={rc} />
      </section>

      {/* Articles */}
      <section className="tt-articles">
        <div className="tt-section-head">
          <div>
            <div className="tt-section-title">Publikacje medialne</div>
            <div className="tt-section-sub">
              Algorytm sentymentu · {filtered.length} z {articles.length}
            </div>
          </div>
          <div className="tt-chart-tabs">
            {filterTabs.map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={'tt-tab' + (filter === k ? ' is-active' : '')}
                onClick={() => setFilter(k)}
              >
                {l}
              </button>
            ))}
          </div>
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
          {filtered.map((a, i) => (
            <ArticleRow
              key={a.id}
              article={a}
              expanded={openId === a.id}
              onToggle={() => setOpenId(openId === a.id ? null : a.id)}
              idx={i}
            />
          ))}
          {filtered.length === 0 && (
            <div className="tt-empty" style={{ padding: 40 }}>
              Brak artykułów spełniających kryteria.
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
