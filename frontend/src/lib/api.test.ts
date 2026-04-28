import { describe, expect, it } from 'vitest';

import { getCompanies, getCompanyArticles, getCompanyRelations, getGraph } from '@/lib/api';

describe('api', () => {
  it('loads companies', async () => {
    const companies = await getCompanies();

    expect(companies.length).toBeGreaterThan(0);
    expect(companies.some((company) => company.id === 'jsw')).toBe(true);
  });

  it('accepts expanded company payload fields', async () => {
    const { http, HttpResponse } = await import('msw');
    const { server } = await import('@/mocks/server');

    server.use(
      http.get('*/api/companies', () => {
        return HttpResponse.json([
          {
            id: 'acme',
            name: 'Acme Holdings S.A.',
            short: 'Acme Holdings',
            nip: '1234567890',
            sector: 'Unknown',
            score: 82,
            trend: 4,
            risk: 'low',
            articles: 1,
            lastUpdate: '2026-04-27T11:00:00',
            history: [61, 64, 66],
            historyByRange: {
              '12M': [61, 64, 66],
              '6M': [64, 66],
              '3M': [61, 64, 66],
              '30D': [66],
            },
            keywords: ['fraud'],
            tradingViewSymbol: 'NASDAQ:ACME',
            hasTradingView: true,
          },
        ]);
      })
    );

    const companies = await getCompanies();

    expect(companies).toHaveLength(1);
    expect(companies[0].tradingViewSymbol).toBe('NASDAQ:ACME');
    expect(companies[0].hasTradingView).toBe(true);
    expect(companies[0].historyByRange?.['6M']).toEqual([64, 66]);
  });

  it('loads relations', async () => {
    const relations = await getCompanyRelations();

    expect(relations.length).toBeGreaterThan(0);
  });

  it('loads articles for jsw', async () => {
    const articles = await getCompanyArticles('jsw');

    expect(articles.length).toBeGreaterThan(0);
    expect(articles[0]).toHaveProperty('headline');
  });

  it('loads mixed graph data for jsw', async () => {
    const graph = await getGraph('jsw');

    expect(graph.rootId).toBe('company:jsw');
    expect(graph.nodes.some((node) => node.entityType === 'Person')).toBe(true);
    expect(graph.nodes.some((node) => node.entityType === 'Event')).toBe(true);
  });

  it('throws on failed response', async () => {
    const { http, HttpResponse } = await import('msw');
    const { server } = await import('@/mocks/server');

    server.use(
      http.get('*/api/companies', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    await expect(getCompanies()).rejects.toThrow(/Request failed: \/api\/companies \(500\)/);
  });

  it('throws when graph request fails', async () => {
    const { http, HttpResponse } = await import('msw');
    const { server } = await import('@/mocks/server');

    server.use(
      http.get('*/api/graph/:companyId', () => {
        return new HttpResponse(null, { status: 503 });
      })
    );

    await expect(getGraph('jsw')).rejects.toThrow(/Request failed: \/api\/graph\/jsw \(503\)/);
  });
});
