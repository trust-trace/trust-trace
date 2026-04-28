import { describe, expect, it } from 'vitest';

describe('GET /api/relations route', () => {
  it('returns company relations from the local dataset', async () => {
    const { GET } = await import('@/app/api/relations/route');
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
  });
});
