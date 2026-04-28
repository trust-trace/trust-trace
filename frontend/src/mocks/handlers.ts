import { HttpResponse, http } from 'msw';

import { ARTICLES, COMPANIES, COMPANY_RELATIONS, GRAPH_RESPONSES } from '@/mocks/data';

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
];
