import { HttpResponse, http } from 'msw';

import { ARTICLES, COMPANIES, COMPANY_RELATIONS, GRAPH_RESPONSES } from '@/mocks/data';

const pipelineRuns = new Map<string, number>();

export const handlers = [
  http.get('*/api/companies', () => {
    return HttpResponse.json(COMPANIES);
  }),
  http.get('*/api/relations', () => {
    return HttpResponse.json(COMPANY_RELATIONS);
  }),
  http.get('*/api/companies/:companyId/articles', ({ params }) => {
    const companyId = String(params.companyId);
    return HttpResponse.json(ARTICLES[companyId] ?? []);
  }),
  http.get('*/api/graph/:companyId', ({ params }) => {
    const companyId = String(params.companyId);
    return HttpResponse.json(GRAPH_RESPONSES[companyId] ?? null);
  }),
  http.post('*/api/pipeline/run', async ({ request }) => {
    const body = (await request.json()) as { query?: string };
    const query = body.query?.trim();

    if (!query) {
      return HttpResponse.json({ detail: "'query' is required" }, { status: 400 });
    }

    const runId = `run-${query.toLowerCase().replace(/\s+/g, '-')}`;
    pipelineRuns.set(runId, 0);

    return HttpResponse.json({ status: 'accepted', run_id: runId }, { status: 202 });
  }),
  http.get('*/api/pipeline/:runId', ({ params }) => {
    const runId = String(params.runId);
    const attempt = (pipelineRuns.get(runId) ?? 0) + 1;
    pipelineRuns.set(runId, attempt);

    return HttpResponse.json({
      run_id: runId,
      query: 'mock query',
      status: attempt > 1 ? 'completed' : 'running',
      phase: attempt > 1 ? 'complete' : 'scraping',
      article_target: 30,
      articles_scraped: attempt > 1 ? 30 : 12,
      articles_processed: attempt > 1 ? 30 : 4,
      firm_ids: [],
      final_scores: {},
      error: null,
      created_at: '2026-04-28T10:00:00.000Z',
      completed_at: attempt > 1 ? '2026-04-28T10:02:00.000Z' : null,
    });
  }),
];
