import { afterEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/graph route', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('proxies graph payload from tarkov backend', async () => {
    vi.stubEnv('TARKOV_API_BASE_URL', 'http://127.0.0.1:8081');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [{ id: 'company:1' }], edges: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { GET } = await import('@/app/api/graph/route');
    const response = await GET();
    const body = await response.json();

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8081/v1/graph', { cache: 'no-store' });
    expect(response.status).toBe(200);
    expect(body).toEqual({ nodes: [{ id: 'company:1' }], edges: [] });
  });

  it('returns backend status when tarkov proxy fails', async () => {
    vi.stubEnv('TARKOV_API_BASE_URL', 'http://127.0.0.1:8081');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => 'neo4j unavailable',
    });
    vi.stubGlobal('fetch', fetchMock);

    const { GET } = await import('@/app/api/graph/route');
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(body).toEqual({ detail: 'neo4j unavailable' });
  });
});
