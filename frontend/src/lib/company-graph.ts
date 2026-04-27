import type { Company, CompanyRelation } from '@/lib/data';

export interface CompanyGraphNode {
  id: string;
  company: Company;
  depth: number;
}

export interface CompanyGraphEdge {
  source: string;
  target: string;
  type: CompanyRelation['type'];
  label?: string;
}

export interface CompanyGraph {
  centerId: string;
  nodes: CompanyGraphNode[];
  edges: CompanyGraphEdge[];
}

function edgeKey(source: string, target: string, type: CompanyRelation['type']): string {
  const [left, right] = [source, target].sort();
  return `${left}:${right}:${type}`;
}

function collectAdjacentEdges(companyId: string, relations: CompanyRelation[]): CompanyRelation[] {
  return relations.filter(
    (relation) =>
      relation.sourceCompanyId === companyId || relation.targetCompanyId === companyId
  );
}

function otherCompanyId(companyId: string, relation: CompanyRelation): string {
  return relation.sourceCompanyId === companyId
    ? relation.targetCompanyId
    : relation.sourceCompanyId;
}

export function buildCompanyGraph(
  companyId: string,
  companies: Company[],
  relations: CompanyRelation[],
  maxDepth = 2
): CompanyGraph {
  const companiesById = new Map(companies.map((company) => [company.id, company]));
  const center = companiesById.get(companyId);

  if (!center) {
    return { centerId: companyId, nodes: [], edges: [] };
  }

  const nodes = new Map<string, CompanyGraphNode>([
    [companyId, { id: companyId, company: center, depth: 0 }],
  ]);
  const edges = new Map<string, CompanyGraphEdge>();
  const queue: Array<{ id: string; depth: number }> = [{ id: companyId, depth: 0 }];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || current.depth >= maxDepth) continue;

    for (const relation of collectAdjacentEdges(current.id, relations)) {
      const nextId = otherCompanyId(current.id, relation);
      const nextCompany = companiesById.get(nextId);
      if (!nextCompany) continue;

      const nextDepth = current.depth + 1;
      const knownNode = nodes.get(nextId);

      if (!knownNode || nextDepth < knownNode.depth) {
        nodes.set(nextId, { id: nextId, company: nextCompany, depth: nextDepth });
        queue.push({ id: nextId, depth: nextDepth });
      }

      if (nextDepth <= maxDepth) {
        const key = edgeKey(relation.sourceCompanyId, relation.targetCompanyId, relation.type);
        if (!edges.has(key)) {
          edges.set(key, {
            source: relation.sourceCompanyId,
            target: relation.targetCompanyId,
            type: relation.type,
            label: relation.label,
          });
        }
      }
    }
  }

  return {
    centerId: companyId,
    nodes: [...nodes.values()].sort((a, b) => {
      if (a.depth !== b.depth) return a.depth - b.depth;
      return a.id.localeCompare(b.id);
    }),
    edges: [...edges.values()].sort((a, b) => {
      const left = `${a.source}:${a.target}:${a.type}`;
      const right = `${b.source}:${b.target}:${b.type}`;
      return left.localeCompare(right);
    }),
  };
}
