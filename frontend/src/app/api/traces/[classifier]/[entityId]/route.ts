import { proxyBackendJson } from '@/lib/backend-api';

export function GET(
  _request: Request,
  { params }: { params: Promise<{ classifier: string; entityId: string }> }
) {
  return params.then(({ classifier, entityId }) =>
    proxyBackendJson(
      `/api/v1/traces/${encodeURIComponent(classifier)}/${encodeURIComponent(entityId)}`
    )
  );
}
