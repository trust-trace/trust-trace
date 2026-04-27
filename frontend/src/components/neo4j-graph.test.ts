import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Neo4jGraphView } from '@/components/neo4j-graph';
import type { Neo4jGraphPayload } from '@/lib/neo4j-graph';

const graph: Neo4jGraphPayload = {
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
};

describe('Neo4jGraphView', () => {
  it('renders loading state', () => {
    const html = renderToStaticMarkup(
      createElement(Neo4jGraphView, { status: 'loading', graph: null, error: null })
    );

    expect(html).toContain('Ładowanie grafu');
  });

  it('renders empty state', () => {
    const html = renderToStaticMarkup(
      createElement(Neo4jGraphView, {
        status: 'success',
        graph: { nodes: [], edges: [] },
        error: null,
      })
    );

    expect(html).toContain('Brak danych grafowych w Neo4j');
  });

  it('renders error state', () => {
    const html = renderToStaticMarkup(
      createElement(Neo4jGraphView, {
        status: 'error',
        graph: null,
        error: 'network down',
      })
    );

    expect(html).toContain('Nie udało się załadować grafu');
    expect(html).toContain('network down');
  });

  it('renders node labels for graph data', () => {
    const html = renderToStaticMarkup(
      createElement(Neo4jGraphView, { status: 'success', graph, error: null })
    );

    expect(html).toContain('Polsat Media Sp. z o.o.');
    expect(html).toContain('Marek Kowalski');
  });
});
