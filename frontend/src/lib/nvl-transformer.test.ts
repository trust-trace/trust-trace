import { describe, expect, it } from 'vitest';

import { transformToNvlGraph } from '@/lib/nvl-transformer';

describe('nvl transformer', () => {
  it('converts Neo4j payloads into NVL nodes and relationships', () => {
    const graph = transformToNvlGraph({
      nodes: [
        {
          id: 'company:1',
          kind: 'company',
          label: 'Polsat Media Sp. z o.o.',
          properties: { company_id: 1 },
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

    expect(graph.nodes).toEqual([
      {
        id: 'company:1',
        label: 'Polsat Media Sp. z o.o.',
        properties: { company_id: 1 },
      },
      {
        id: 'person:1',
        label: 'Marek Kowalski',
        properties: { person_id: 1 },
      },
    ]);

    expect(graph.relationships).toEqual([
      {
        id: 'rel:31',
        type: 'AFFILIATED_WITH',
        from: 'company:1',
        to: 'person:1',
        properties: { role: 'CEO' },
      },
    ]);
  });
});
