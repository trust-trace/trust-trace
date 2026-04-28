import { proxyBackendJson } from '@/lib/backend-api';

export function GET(
  _request: Request,
  { params }: { params: Promise<{ companyId: string }> }
) {
  return params.then(({ companyId }) =>
    proxyBackendJson(`/api/graph/${encodeURIComponent(companyId)}`)
  );
}
