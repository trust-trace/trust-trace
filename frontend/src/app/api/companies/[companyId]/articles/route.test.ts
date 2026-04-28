import { describe, expect, it } from 'vitest';

describe('GET /api/companies/:companyId/articles route', () => {
  it('returns articles for the requested company', async () => {
    const { GET } = await import('@/app/api/companies/[companyId]/articles/route');
    const response = await GET(new Request('http://localhost'), {
      params: Promise.resolve({ companyId: 'jsw' }),
    } as never);
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.length).toBeGreaterThan(0);
    expect(body[0]).toHaveProperty('headline');
  });

  it('returns an empty list for unknown companies', async () => {
    const { GET } = await import('@/app/api/companies/[companyId]/articles/route');
    const response = await GET(new Request('http://localhost'), {
      params: Promise.resolve({ companyId: 'missing' }),
    } as never);
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual([]);
  });
});
