import { describe, expect, it } from 'vitest';
import { COMPANY_RELATIONS, COMPANIES } from '@/lib/data';
import { buildCompanyGraph } from '@/lib/company-graph';

describe('buildCompanyGraph', () => {
  it('returns the selected company with only depth-1 and depth-2 connections', () => {
    const graph = buildCompanyGraph('allegro', COMPANIES, COMPANY_RELATIONS, 2);

    expect(graph.centerId).toBe('allegro');
    expect(graph.nodes.map((node) => [node.id, node.depth])).toEqual([
      ['allegro', 0],
      ['cyfrowy', 1],
      ['dino', 1],
      ['lpp', 1],
      ['asseco', 2],
      ['orlen', 2],
      ['pko', 2],
    ]);
    expect(graph.edges.map((edge) => [edge.source, edge.target, edge.type])).toEqual([
      ['allegro', 'cyfrowy', 'business'],
      ['allegro', 'dino', 'partnership'],
      ['allegro', 'lpp', 'person'],
      ['cyfrowy', 'pko', 'business'],
      ['dino', 'asseco', 'business'],
      ['lpp', 'orlen', 'partnership'],
    ]);
  });

  it('returns only the center node when no relations exist', () => {
    const graph = buildCompanyGraph('getin', COMPANIES, COMPANY_RELATIONS, 2);

    expect(graph.nodes.map((node) => node.id)).toEqual(['getin']);
    expect(graph.edges).toEqual([]);
  });
});
