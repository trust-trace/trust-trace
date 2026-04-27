'use client';

import { useEffect, useState } from 'react';
import { Topbar } from '@/components/topbar';
import { Sidebar } from '@/components/sidebar';
import { MainPanel } from '@/components/main-panel';
import { getCompanies, getCompanyArticles, getCompanyRelations } from '@/lib/api';
import type { Article, Company, CompanyRelation } from '@/lib/data';

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [relations, setRelations] = useState<CompanyRelation[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [selectedId, setSelectedId] = useState('jsw');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function handleSelectCompany(nextCompanyId: string) {
    setArticles([]);
    setError(null);
    setSelectedId(nextCompanyId);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      setLoading(true);
      setError(null);

      try {
        const [nextCompanies, nextRelations] = await Promise.all([
          getCompanies(),
          getCompanyRelations(),
        ]);

        if (cancelled) return;

        setCompanies(nextCompanies);
        setRelations(nextRelations);

        const defaultSelectedId = nextCompanies.some((company) => company.id === 'jsw')
          ? 'jsw'
          : nextCompanies[0]?.id ?? '';

        setSelectedId(defaultSelectedId);
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : 'Unknown error');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadInitialData();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    let cancelled = false;

    async function loadArticles() {
      setError(null);

      try {
        const nextArticles = await getCompanyArticles(selectedId);

        if (!cancelled) {
          setArticles(nextArticles);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : 'Unknown error');
        }
      }
    }

    loadArticles();

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const company = companies.find((currentCompany) => currentCompany.id === selectedId) ?? companies[0] ?? null;

  if (loading) {
    return (
      <div className="tt-root">
        <div className="tt-empty" style={{ padding: 40 }}>Ładowanie danych…</div>
      </div>
    );
  }

  if (error && !company) {
    return (
      <div className="tt-root">
        <div className="tt-empty" style={{ padding: 40 }}>
          <p>Nie udało się załadować danych: {error}</p>
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
      {error && company && (
        <div className="tt-empty" style={{ margin: '0 24px', padding: 16 }}>
          Nie udało się pobrać części danych: {error}
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
            companies={companies}
            articles={articles}
            relations={relations}
            onSelectCompany={handleSelectCompany}
          />
        )}
      </div>
    </div>
  );
}
