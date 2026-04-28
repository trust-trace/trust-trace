import type {
  Article,
  Company,
  CompanyRelation,
  GraphResponse,
  IngestionStats,
  PipelineRunAccepted,
  PipelineRunStatus,
  ReasoningTrace,
} from '@/lib/data';

function toRequestUrl(input: string): URL | string {
  if (/^https?:\/\//.test(input)) {
    return input;
  }

  const base = typeof window === 'undefined' ? 'http://localhost' : window.location.origin;
  return new URL(input, base);
}

async function readJson<T>(input: string): Promise<T> {
  const response = await fetch(toRequestUrl(input));

  if (!response.ok) {
    throw new Error(`Request failed: ${input} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

async function sendJson<T>(input: string, init: RequestInit): Promise<T> {
  const response = await fetch(toRequestUrl(input), init);

  if (!response.ok) {
    throw new Error(`Request failed: ${input} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export function getCompanies() {
  return readJson<Company[]>('/api/companies');
}

export function getIngestionStats() {
  return readJson<IngestionStats>('/api/ingestion/stats');
}

export function getCompanyArticles(companyId: string) {
  return readJson<Article[]>(`/api/companies/${companyId}/articles`);
}

export function getCompanyRelations() {
  return readJson<CompanyRelation[]>('/api/relations');
}

export function getGraph(companyId: string) {
  return readJson<GraphResponse>(`/api/graph/${companyId}`);
}

export function runPipeline(query: string, articleLimit = 30) {
  return sendJson<PipelineRunAccepted>('/api/pipeline/run', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({ query, article_limit: articleLimit }),
  });
}

export function getPipelineRun(runId: string) {
  return readJson<PipelineRunStatus>(`/api/pipeline/${runId}`);
}

export function getTracesByCorrelation(correlationId: string) {
  return readJson<ReasoningTrace[]>(
    `/api/traces/correlation/${encodeURIComponent(correlationId)}`
  );
}

export function getTraces(classifier: string, entityId: string) {
  return readJson<ReasoningTrace[]>(
    `/api/traces/${encodeURIComponent(classifier)}/${encodeURIComponent(entityId)}`
  );
}

export function getCompanyTraces(companySlug: string) {
  return readJson<ReasoningTrace[]>(
    `/api/traces/company/${encodeURIComponent(companySlug)}`
  );
}
