import { proxyBackendJson } from '@/lib/backend-api';

export function GET(
  _request: Request,
  { params }: { params: Promise<{ correlationId: string }> }
) {
  return params.then(({ correlationId }) =>
    proxyBackendJson(`/api/v1/traces/correlation/${encodeURIComponent(correlationId)}`)
  );
}
