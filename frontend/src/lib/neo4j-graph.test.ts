import { describe, expect, it } from 'vitest';

import { getConnectedNodeIds, toEdgeKey, type Neo4jGraphPayload } from '@/lib/neo4j-graph';

const payload: Neo4jGraphPayload = {
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
    {
      id: 'event:evt-001',
      kind: 'event',
      label: 'FAKE_INVOICES',
      properties: { event_id: 'evt-001' },
    },
  ],
  edges: [
    {
      id: 'rel:1',
      source: 'company:1',
      target: 'person:1',
      type: 'AFFILIATED_WITH',
      properties: { role: 'CEO' },
    },
    {
      id: 'rel:2',
      source: 'person:1',
      target: 'event:evt-001',
      type: 'INVOLVED_IN',
      properties: { role_in_event: 'orchestrator' },
    },
  ],
};

describe('neo4j graph helpers', () => {
  it('creates stable edge keys', () => {
    expect(toEdgeKey(payload.edges[0])).toBe('rel:1');
  });

  it('collects connected node ids for a hovered node', () => {
    expect([...getConnectedNodeIds('person:1', payload.edges)].sort()).toEqual([
      'company:1',
      'event:evt-001',
      'person:1',
    ]);
  });
});
