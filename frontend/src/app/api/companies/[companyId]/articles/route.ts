import { proxyBackendJson } from '@/lib/backend-api';

type RouteContext = {
  params: Promise<{
    companyId: string;
  }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { companyId } = await context.params;
  return proxyBackendJson(`/api/companies/${encodeURIComponent(companyId)}/articles`);
}
