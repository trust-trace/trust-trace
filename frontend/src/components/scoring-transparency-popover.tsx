'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import type { Article } from '@/lib/data';

interface ScoringTransparencyPopoverProps {
  article: Article;
}

export function ScoringTransparencyPopover({ article }: ScoringTransparencyPopoverProps) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const sources = article.sources ?? [];
  const traces = article.traces ?? [];
  const sourceText = (article.sourceText ?? '').trim();

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;

    const update = () => {
      const btn = btnRef.current;
      if (!btn) return;
      const r = btn.getBoundingClientRect();
      const popW = 380;
      let left = r.left + r.width / 2 - popW / 2;
      left = Math.max(12, Math.min(left, window.innerWidth - popW - 12));
      setCoords({ top: r.bottom + 8, left });
    };

    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      const el = e.target as Node;
      if (btnRef.current?.contains(el) || panelRef.current?.contains(el)) return;
      setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  const panel = open ? (
    <>
      <div
        className="tt-score-pop-backdrop"
        aria-hidden
        onClick={() => setOpen(false)}
      />
      <div
        ref={panelRef}
        className="tt-score-pop"
        style={{ top: coords.top, left: coords.left }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tt-score-pop-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="tt-score-pop-head">
          <h2 id="tt-score-pop-title" className="tt-score-pop-title">
            Uzasadnienie wpływu na scoring
          </h2>
          <p className="tt-score-pop-sub">
            Pełna widoczność: źródła, cytat użyty w modelu oraz zapisane trace decyzyjne.
          </p>
        </div>

        <div className="tt-score-pop-body">
          <section className="tt-score-pop-section">
            <h3 className="tt-score-pop-h3">Tekst źródłowy (source_text)</h3>
            {sourceText ? (
              <blockquote className="tt-score-pop-quote">{sourceText}</blockquote>
            ) : (
              <p className="tt-score-pop-empty">Brak zapisu cytatu w danych z backendu.</p>
            )}
          </section>

          <section className="tt-score-pop-section">
            <h3 className="tt-score-pop-h3">Źródła</h3>
            {sources.length > 0 ? (
              <ul className="tt-score-pop-sources">
                {sources.map((s) => (
                  <li key={s.url}>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="tt-score-pop-link"
                    >
                      {s.title || s.url}
                    </a>
                    <div className="tt-score-pop-meta">
                      <span className="tt-mono">{s.sourceCategory}</span>
                      {s.publishedAt && (
                        <span className="tt-mono">{s.publishedAt}</span>
                      )}
                      {s.credibility != null && (
                        <span>wiarygodność: {s.credibility.toFixed(2)}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="tt-score-pop-empty">Brak listy źródeł w odpowiedzi API.</p>
            )}
          </section>

          <section className="tt-score-pop-section">
            <h3 className="tt-score-pop-h3">Trace</h3>
            {traces.length > 0 ? (
              <div className="tt-score-pop-traces">
                {traces.map((t, idx) => (
                  <div key={`${t.classifier_name}-${t.created_at}-${idx}`} className="tt-score-pop-trace">
                    <div className="tt-score-pop-trace-head">
                      <span className="tt-score-pop-badge">{t.classifier_name}</span>
                      <span className="tt-mono tt-score-pop-trace-meta">{t.entity_type}</span>
                      <span className="tt-mono tt-score-pop-trace-meta">{t.entity_id}</span>
                      {t.correlation_id ? (
                        <span className="tt-mono tt-score-pop-trace-meta">
                          corr: {t.correlation_id}
                        </span>
                      ) : null}
                      <span className="tt-mono tt-score-pop-trace-meta">{t.created_at}</span>
                    </div>
                    <pre className="tt-score-pop-pre">
                      {JSON.stringify(t.trace_data, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tt-score-pop-empty">
                Brak trace dla tego zdarzenia (np. pipeline nie zapisał jeszcze rekordów).
              </p>
            )}
          </section>
        </div>
      </div>
    </>
  ) : null;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className="tt-score-info-btn"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Otwórz uzasadnienie wpływu na scoring: źródła, tekst źródłowy, trace"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.75" />
          <path
            d="M12 16v-5M12 8h.01"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
      </button>
      {typeof document !== 'undefined' && panel ? createPortal(panel, document.body) : null}
    </>
  );
}
