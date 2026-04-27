'use client';

import { useState, useEffect } from 'react';
import type { Article } from '@/lib/data';
import { SentimentBar, sentimentColor, sentimentLabel } from './sentiment-bar';

function formatDate(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()} · ${hh}:${min}`;
}

function calcRelativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'przed chwilą';
  if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h temu`;
  const days = Math.floor(diff / 86400);
  if (days === 1) return '1 dzień temu';
  return `${days} dni temu`;
}

function useRelativeTime(iso: string): string {
  // Render empty on server to avoid hydration mismatch, fill in on client.
  const [label, setLabel] = useState('');
  useEffect(() => {
    setLabel(calcRelativeTime(iso));
    const id = setInterval(() => setLabel(calcRelativeTime(iso)), 60_000);
    return () => clearInterval(id);
  }, [iso]);
  return label;
}

interface ArticleRowProps {
  article: Article;
  expanded: boolean;
  onToggle: () => void;
  idx: number;
}

export function ArticleRow({ article, expanded, onToggle, idx }: ArticleRowProps) {
  const sc = sentimentColor(article.sentiment);
  const relTime = useRelativeTime(article.date);

  return (
    <div
      className={'tt-art' + (expanded ? ' is-open' : '')}
      style={{ animationDelay: `${idx * 35}ms` }}
    >
      {/*
        tt-art-head is a CSS grid row. To avoid invalid HTML (button > div),
        we use a div with onClick + onKeyDown for keyboard accessibility.
      */}
      <div
        className="tt-art-head"
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{ cursor: 'pointer' }}
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
      >
        <div className="tt-art-chev">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <path d="m9 6 6 6-6 6" />
          </svg>
        </div>
        <div className="tt-art-headline">{article.headline}</div>
        <div className="tt-art-source">
          <span className={`tt-tier tt-${article.sourceTier}`} />
          {article.source}
        </div>
        <div className="tt-art-date tt-mono">{relTime}</div>
        <div className="tt-art-sent" style={{ color: sc }}>
          <span className="tt-sent-dot" style={{ background: sc }} />
          {sentimentLabel(article.sentiment)}
        </div>
        <div className={'tt-art-impact tt-mono' + (article.impact < 0 ? ' is-neg' : ' is-pos')}>
          {article.impact > 0 ? '+' : ''}
          {article.impact.toFixed(1)}
        </div>
      </div>

      <div className="tt-art-body">
        <div className="tt-art-body-inner">
          <div className="tt-art-grid">
            <div className="tt-art-excerpt">
              <div className="tt-art-label">Fragment</div>
              <p>{article.excerpt}</p>

              <div className="tt-art-label" style={{ marginTop: 18 }}>
                Słowa kluczowe ryzyka
              </div>
              <div className="tt-keywords">
                {article.keywords.map((k) => (
                  <span key={k} className="tt-kw">
                    {k}
                  </span>
                ))}
              </div>

              <div className="tt-art-label" style={{ marginTop: 18 }}>
                Encje rozpoznane
              </div>
              <div className="tt-entities">
                {article.entities.map((e) => (
                  <span key={e} className="tt-entity">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                      <circle cx="12" cy="8" r="4" />
                      <path d="M4 21v-1a8 8 0 0 1 16 0v1" />
                    </svg>
                    {e}
                  </span>
                ))}
              </div>
            </div>

            <div className="tt-art-meta">
              <div className="tt-art-label">Sentyment artykułu</div>
              <SentimentBar value={article.sentiment} />

              <div className="tt-art-label" style={{ marginTop: 18 }}>
                Wpływ na scoring
              </div>
              <div
                className="tt-impact-big"
                style={{
                  color:
                    article.impact < 0
                      ? 'oklch(0.55 0.18 25)'
                      : 'oklch(0.55 0.13 155)',
                }}
              >
                {article.impact > 0 ? '+' : ''}
                {article.impact.toFixed(1)}
                <span className="tt-impact-unit">pkt</span>
              </div>

              <div className="tt-art-meta-rows">
                <div>
                  <span>Data publikacji</span>
                  <span className="tt-mono">{formatDate(article.date)}</span>
                </div>
                <div>
                  <span>Wiarygodność źródła</span>
                  <span>
                    {article.sourceTier === 'tier-1'
                      ? 'Wysoka'
                      : article.sourceTier === 'tier-2'
                        ? 'Średnia'
                        : 'Standard'}
                  </span>
                </div>
                <div>
                  <span>Identyfikator</span>
                  <span className="tt-mono">{article.id.toUpperCase()}</span>
                </div>
              </div>

              <div className="tt-art-actions">
                <button type="button" className="tt-btn-ghost">Otwórz źródło ↗</button>
                <button type="button" className="tt-btn-ghost">Eksportuj raport</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
