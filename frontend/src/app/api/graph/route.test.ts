import { afterEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/graph route', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('proxies graph payload from tarkov backend when available', async () => {
    vi.stubEnv('TARKOV_API_BASE_URL', 'http://127.0.0.1:8081');
    const backendPayload = { nodes: [{ id: 'company:1' }], edges: [] };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => backendPayload,
    });
    vi.stubGlobal('fetch', fetchMock);

    const { GET } = await import('@/app/api/graph/route');
    const response = await GET();
    const body = await response.json();

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8081/v1/graph', { cache: 'no-store' });
    expect(response.status).toBe(200);
    expect(body).toEqual(backendPayload);
  });

  it('returns mock data when tarkov backend is unavailable', async () => {
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

    expect(response.status).toBe(200);
    expect(body.nodes).toBeDefined();
    expect(body.edges).toBeDefined();
    expect(body.nodes.length).toBeGreaterThan(0);
    expect(body.edges.length).toBeGreaterThan(0);
  });

  it('returns mock data when network request fails', async () => {
    vi.stubEnv('TARKOV_API_BASE_URL', 'http://127.0.0.1:8081');
    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);

    const { GET } = await import('@/app/api/graph/route');
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.nodes).toBeDefined();
    expect(body.edges).toBeDefined();
  });
});
