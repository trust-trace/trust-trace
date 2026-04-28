'use client';

interface AnalysisLauncherProps {
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  busy: boolean;
  status: string | null;
  error: string | null;
  compact?: boolean;
}

export function AnalysisLauncher({
  query,
  onQueryChange,
  onSubmit,
  busy,
  status,
  error,
  compact = false,
}: AnalysisLauncherProps) {
  return (
    <section className={'tt-analysis-launcher' + (compact ? ' is-compact' : '')}>
      <div className="tt-analysis-copy">
        <div className="tt-analysis-eyebrow">Pipeline</div>
        <h2 className="tt-analysis-title">Uruchom analizę firmy lub frazy</h2>
        <p className="tt-analysis-sub">
          Wpisz nazwę podmiotu albo słowo kluczowe, aby wystartować pełny przebieg analizy.
        </p>
      </div>

      <form
        className="tt-analysis-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit();
        }}
      >
        <input
          className="tt-analysis-input"
          type="text"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="np. Cyfrowy Polsat, AML, Orlen"
          spellCheck={false}
          aria-label="Fraza do analizy"
          disabled={busy}
        />
        <button type="submit" className="tt-analysis-button" disabled={busy || !query.trim()}>
          {busy ? 'Uruchamianie…' : 'Start analysis'}
        </button>
      </form>

      {status && <div className="tt-analysis-status">{status}</div>}
      {error && <div className="tt-analysis-error">{error}</div>}
    </section>
  );
}
