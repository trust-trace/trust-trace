'use client';

import { useState, useEffect } from 'react';

import { getIngestionStats } from '@/lib/api';
import type { IngestionStats } from '@/lib/data';

const INGESTION_POLL_MS = 2500;

export function Topbar() {
  const [time, setTime] = useState('');
  const [ingestion, setIngestion] = useState<IngestionStats | null>(null);

  useEffect(() => {
    function tick() {
      const d = new Date();
      setTime(
        `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
      );
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const next = await getIngestionStats();
        if (!cancelled) setIngestion(next);
      } catch {
        /* keep last successful snapshot */
      }
    }

    poll();
    const id = setInterval(poll, INGESTION_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const busy = ingestion !== null && (ingestion.queued > 0 || ingestion.parsing > 0);

  return (
    <div className="tt-topbar">
      <div className="tt-logo">
        <span className="tt-logo-mark">tt</span>
        <span>
          trust<span className="tt-logo-italic">·</span>
          <i>trace</i>
        </span>
      </div>
      <div className="tt-topbar-right">
        <span
          className={`tt-pill tt-ingestion-pill${busy ? ' tt-ingestion-pill--busy' : ''}`}
          title="Artykuły oczekujące w kolejce ingestion oraz aktualnie przetwarzane przez worker"
        >
          <span className="tt-mono">{ingestion?.queued ?? '–'}</span>
          <span className="tt-ingestion-pill-label">w kolejce</span>
          <span className="tt-ingestion-pill-sep">·</span>
          <span className="tt-mono">{ingestion?.parsing ?? '–'}</span>
          <span className="tt-ingestion-pill-label">parsowanie</span>
        </span>
        <span className="tt-pill">
          <span className="tt-live-dot" />
          Live · 38 źródeł
        </span>
        <span className="tt-mono" style={{ color: 'var(--tt-fg-mute)', fontSize: 11 }}>
          {time}
        </span>
        <div className="tt-avatar">MK</div>
      </div>
    </div>
  );
}
