import { HttpResponse, http } from 'msw';

import { ARTICLES, COMPANIES, COMPANY_RELATIONS } from '@/mocks/data';

export const handlers = [
  http.get('*/api/companies', () => {
    return HttpResponse.json(COMPANIES);
  }),
  http.get('*/api/relations', () => {
    return HttpResponse.json(COMPANY_RELATIONS);
  }),
  http.get('*/api/graph', () => {
    return HttpResponse.json({
      nodes: [
        {
          id: 'company:1',
          kind: 'company',
          label: 'Polsat Media Sp. z o.o.',
          properties: { company_id: 1, country: 'PL' },
        },
        {
          id: 'person:1',
          kind: 'person',
          label: 'Marek Kowalski',
          properties: { person_id: 1 },
        },
      ],
      edges: [
        {
          id: 'rel:31',
          source: 'company:1',
          target: 'person:1',
          type: 'AFFILIATED_WITH',
          properties: { role: 'CEO' },
        },
      ],
    });
  }),
  http.get('*/api/companies/:companyId/articles', ({ params }) => {
    const companyId = String(params.companyId);
    return HttpResponse.json(ARTICLES[companyId] ?? []);
  }),
];
