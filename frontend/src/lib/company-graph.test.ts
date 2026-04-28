import { describe, expect, it } from 'vitest';
import { GRAPH_RESPONSES } from '@/mocks/data';
import { normalizeEntityGraph, rerootEntityGraph } from '@/lib/entity-graph';

describe('normalizeEntityGraph', () => {
  it('preserves ids and sorts nodes by depth then type', () => {
    const graph = normalizeEntityGraph(GRAPH_RESPONSES.jsw);

    expect(graph.rootId).toBe('company:jsw');
    expect(graph.nodes.map((node) => [node.id, node.depth, node.entityType])).toEqual([
      ['company:jsw', 0, 'Company'],
      ['company:orlen', 1, 'Company'],
      ['person:anna-nowak', 1, 'Person'],
      ['person:jan-kowalski', 1, 'Person'],
      ['event:cba-investigation', 1, 'Event'],
      ['company:tauron', 2, 'Company'],
      ['event:labour-strike', 2, 'Event'],
    ]);
    expect(graph.nodes[0].summary).toContain('Trust');
    expect(graph.nodes[2].badge).toBe('44');
    expect(graph.nodes[2].tintRisk).toBe('medium');
    expect(graph.nodes[2].summary).toContain('Trust 44');
  });

  it('maps edge presentation metadata from relationship type', () => {
    const graph = normalizeEntityGraph(GRAPH_RESPONSES.jsw);

    expect(graph.edges.map((edge) => [edge.relationshipType, edge.dashArray, edge.width > 2])).toEqual([
      ['CONNECTION', '', true],
      ['ABOUT', '2 4', false],
      ['AFFILIATED_WITH', '', false],
      ['AFFILIATED_WITH', '', false],
      ['CONNECTION', '', true],
      ['INVOLVED_IN', '5 4', false],
      ['INVOLVED_IN', '5 4', false],
    ]);
  });

  it('handles incomplete optional fields safely', () => {
    const graph = normalizeEntityGraph({
      rootId: 'company:test',
      nodes: [
        {
          id: 'company:test',
          entityType: 'Company',
          entityId: 'test',
          depth: 0,
          label: 'Test',
          data: {},
        },
        {
          id: 'event:test',
          entityType: 'Event',
          entityId: 'evt',
          depth: 1,
          label: 'Event',
          data: {},
        },
      ],
      edges: [
        {
          id: 'company:test->event:test:ABOUT:-',
          source: 'company:test',
          target: 'event:test',
          relationshipType: 'ABOUT',
          connectionType: '',
          intensity: null,
          label: '',
          sourceUrl: '',
          sourceTitle: '',
        },
      ],
    });

    expect(graph.nodes[0].summary).toContain('Trust');
    expect(graph.nodes[1].badge).toBeNull();
    expect(graph.edges[0].summary).toBe('Publikacja o zdarzeniu');
  });

  it('uses backend-provided event risk when present', () => {
    const graph = normalizeEntityGraph({
      rootId: 'company:test',
      nodes: [
        {
          id: 'company:test',
          entityType: 'Company',
          entityId: 'test',
          depth: 0,
          label: 'Test',
          data: {},
        },
        {
          id: 'event:test',
          entityType: 'Event',
          entityId: 'evt',
          depth: 1,
          label: 'Event',
          data: { riskLevel: 1, risk: 'high' },
        },
      ],
      edges: [
        {
          id: 'company:test->event:test:ABOUT:-',
          source: 'company:test',
          target: 'event:test',
          relationshipType: 'ABOUT',
          connectionType: '',
          intensity: null,
          label: '',
          sourceUrl: '',
          sourceTitle: '',
        },
      ],
    });

    expect(graph.nodes[1].tintRisk).toBe('high');
  });

  it('can reroot the graph around any node, including events', () => {
    const graph = rerootEntityGraph(normalizeEntityGraph(GRAPH_RESPONSES.jsw), 'event:cba-investigation');

    expect(graph.rootId).toBe('event:cba-investigation');
    expect(graph.nodes.map((node) => [node.id, node.depth])).toEqual([
      ['event:cba-investigation', 0],
      ['company:jsw', 1],
      ['person:jan-kowalski', 1],
      ['company:orlen', 2],
      ['person:anna-nowak', 2],
      ['company:tauron', 3],
      ['event:labour-strike', 3],
    ]);
    expect(
      graph.edges.find((edge) => edge.id === 'company:jsw->event:cba-investigation:ABOUT:-')
    ).toMatchObject({
      source: 'event:cba-investigation',
      target: 'company:jsw',
    });
    expect(
      graph.edges.find((edge) => edge.id === 'person:jan-kowalski->event:cba-investigation:INVOLVED_IN:-')
    ).toMatchObject({
      source: 'event:cba-investigation',
      target: 'person:jan-kowalski',
    });
  });
});
