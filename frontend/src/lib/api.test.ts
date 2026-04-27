import { describe, expect, it } from 'vitest';

import { getCompanies, getCompanyArticles, getCompanyRelations } from '@/lib/api';

describe('api', () => {
  it('loads companies', async () => {
    const companies = await getCompanies();

    expect(companies.length).toBeGreaterThan(0);
    expect(companies.some((company) => company.id === 'jsw')).toBe(true);
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
});
