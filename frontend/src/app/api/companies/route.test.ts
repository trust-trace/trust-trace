import { describe, expect, it } from 'vitest';

describe('GET /api/companies route', () => {
  it('returns companies from the local dataset', async () => {
    const { GET } = await import('@/app/api/companies/route');
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(Array.isArray(body)).toBe(true);
    expect(body.some((company: { id: string }) => company.id === 'jsw')).toBe(true);
  });
});
