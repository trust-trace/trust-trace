'use client';

import { useEffect, useState } from 'react';
import { Topbar } from '@/components/topbar';
import { Sidebar } from '@/components/sidebar';
import { MainPanel } from '@/components/main-panel';
import { getCompanies, getCompanyArticles } from '@/lib/api';
import type { Article, Company } from '@/lib/data';

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [loadingArticles, setLoadingArticles] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [articleError, setArticleError] = useState<string | null>(null);

  function handleSelectCompany(nextCompanyId: string) {
    setArticles([]);
    setArticleError(null);
    setSelectedId(nextCompanyId);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      setLoadingCompanies(true);
      setCompanyError(null);

      try {
        const nextCompanies = await getCompanies();

        if (cancelled) return;

        setCompanies(nextCompanies);

        const defaultSelectedId = nextCompanies.some((company) => company.id === 'jsw')
          ? 'jsw'
          : nextCompanies[0]?.id ?? '';

        setSelectedId(defaultSelectedId);
      } catch (nextError) {
        if (!cancelled) {
          setCompanyError(nextError instanceof Error ? nextError.message : 'Unknown error');
        }
      } finally {
        if (!cancelled) {
          setLoadingCompanies(false);
        }
      }
    }

    loadInitialData();

    return () => {
      cancelled = true;
    };
  }, []);

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

    loadArticles();

    return () => {
      cancelled = true;
    };
  }, [companies, selectedId]);

  const company = companies.find((currentCompany) => currentCompany.id === selectedId) ?? companies[0] ?? null;

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
        />
        {company && (
          <MainPanel
            company={company}
            articles={articles}
            articlesLoading={loadingArticles}
            articleError={articleError}
            onSelectCompany={handleSelectCompany}
          />
        )}
      </div>
    </div>
  );
}
