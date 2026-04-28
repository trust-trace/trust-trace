'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AnalysisLauncher } from '@/components/analysis-launcher';
import { Topbar } from '@/components/topbar';
import { Sidebar } from '@/components/sidebar';
import { MainPanel } from '@/components/main-panel';
import { getCompanies, getCompanyArticles, getPipelineRun, runPipeline } from '@/lib/api';
import type { Article, Company, PipelineRunStatus } from '@/lib/data';

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [loadingArticles, setLoadingArticles] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [articleError, setArticleError] = useState<string | null>(null);
  const [analysisQuery, setAnalysisQuery] = useState('');
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [pipelineRunId, setPipelineRunId] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineRunStatus | null>(null);

  const loadCompanies = useCallback(async () => {
    setLoadingCompanies(true);
    setCompanyError(null);

    try {
      const nextCompanies = await getCompanies();

      setCompanies(nextCompanies);
      setSelectedId((currentSelectedId) => {
        if (nextCompanies.some((company) => company.id === currentSelectedId)) {
          return currentSelectedId;
        }

        if (nextCompanies.some((company) => company.id === 'jsw')) {
          return 'jsw';
        }

        return nextCompanies[0]?.id ?? '';
      });
    } catch (nextError) {
      setCompanyError(nextError instanceof Error ? nextError.message : 'Unknown error');
    } finally {
      setLoadingCompanies(false);
    }
  }, []);

  const handleSelectCompany = useCallback((nextCompanyId: string) => {
    setArticles([]);
    setArticleError(null);
    setSelectedId(nextCompanyId);
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    const query = analysisQuery.trim();

    if (!query) {
      setAnalysisError('Wpisz nazwę firmy albo słowo kluczowe.');
      return;
    }

    setAnalysisBusy(true);
    setAnalysisError(null);

    try {
      const response = await runPipeline(query);
      setPipelineRunId(response.run_id);
      setPipelineStatus(null);
    } catch (nextError) {
      setAnalysisBusy(false);
      setAnalysisError(nextError instanceof Error ? nextError.message : 'Unknown error');
    }
  }, [analysisQuery]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      await loadCompanies();

      if (cancelled) {
        return;
      }
    }

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, [loadCompanies]);

  useEffect(() => {
    if (!selectedId || !companies.some((company) => company.id === selectedId)) {
      return;
    }

    let cancelled = false;

    async function loadArticles() {
      setLoadingArticles(true);
      setArticleError(null);

      try {
        const nextArticles = await getCompanyArticles(selectedId);

        if (!cancelled) {
          setArticles(nextArticles);
        }
      } catch (nextError) {
        if (!cancelled) {
          setArticles([]);
          setArticleError(nextError instanceof Error ? nextError.message : 'Unknown error');
        }
      } finally {
        if (!cancelled) {
          setLoadingArticles(false);
        }
      }
    }

    void loadArticles();

    return () => {
      cancelled = true;
    };
  }, [companies, selectedId]);

  useEffect(() => {
    if (!pipelineRunId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | undefined;

    const poll = async () => {
      try {
        const nextStatus = await getPipelineRun(pipelineRunId);

        if (cancelled) {
          return;
        }

        setPipelineStatus(nextStatus);

        if (nextStatus.status === 'failed') {
          setAnalysisBusy(false);
          setAnalysisError(nextStatus.error ?? 'Pipeline failed');
          return;
        }

        if (nextStatus.status === 'completed') {
          setAnalysisBusy(false);
          await loadCompanies();
          return;
        }

        if (companies.length === 0) {
          await loadCompanies();
        }

        timeoutId = window.setTimeout(() => {
          void poll();
        }, 3000);
      } catch (nextError) {
        if (!cancelled) {
          setAnalysisBusy(false);
          setAnalysisError(nextError instanceof Error ? nextError.message : 'Unknown error');
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [companies.length, loadCompanies, pipelineRunId]);

  const company = companies.find((currentCompany) => currentCompany.id === selectedId) ?? companies[0] ?? null;
  const analysisStatus = useMemo(() => {
    if (analysisBusy && !pipelineStatus && pipelineRunId) {
      return `Run ${pipelineRunId} accepted. Waiting for first pipeline update…`;
    }

    if (!pipelineStatus) {
      return null;
    }

    if (pipelineStatus.status === 'completed') {
      return `Analiza zakończona. Run ${pipelineStatus.run_id} ukończył etap ${pipelineStatus.phase}.`;
    }

    if (pipelineStatus.status === 'failed') {
      return `Run ${pipelineStatus.run_id} zatrzymał się na etapie ${pipelineStatus.phase}.`;
    }

    return `Run ${pipelineStatus.run_id} · ${pipelineStatus.phase} · ${pipelineStatus.articles_processed}/${pipelineStatus.article_target} przetworzonych artykułów`;
  }, [analysisBusy, pipelineRunId, pipelineStatus]);

  if (loadingCompanies) {
    return (
      <div className="tt-root">
        <div className="tt-empty" style={{ padding: 40 }}>Ładowanie danych…</div>
      </div>
    );
  }

  if (companyError && !company) {
    return (
      <div className="tt-root">
        <div className="tt-empty" style={{ padding: 40 }}>
          <p>Nie udało się załadować danych: {companyError}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Spróbuj ponownie
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="tt-root">
      <Topbar />
      {companyError && company && (
        <div className="tt-empty" style={{ margin: '0 24px', padding: 16 }}>
          Nie udało się pobrać części danych: {companyError}
        </div>
      )}
      <div className="tt-app-body">
        <Sidebar
          companies={companies}
          selectedId={company?.id ?? ''}
          onSelect={handleSelectCompany}
          analysisQuery={analysisQuery}
          onAnalysisQueryChange={setAnalysisQuery}
          onStartAnalysis={handleStartAnalysis}
          analysisBusy={analysisBusy}
          analysisStatus={analysisStatus}
          analysisError={analysisError}
        />
        {company ? (
          <MainPanel
            company={company}
            articles={articles}
            articlesLoading={loadingArticles}
            articleError={articleError}
            onSelectCompany={handleSelectCompany}
          />
        ) : (
          <main className="tt-main tt-main-empty-state">
            <AnalysisLauncher
              query={analysisQuery}
              onQueryChange={setAnalysisQuery}
              onSubmit={handleStartAnalysis}
              busy={analysisBusy}
              status={analysisStatus}
              error={analysisError ?? companyError}
            />
          </main>
        )}
      </div>
    </div>
  );
}
