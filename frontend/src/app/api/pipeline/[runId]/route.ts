import { proxyBackend } from '@/lib/backend-api';

export function GET(
  _request: Request,
  { params }: { params: Promise<{ runId: string }> }
) {
  return params.then(({ runId }) => proxyBackend(`/v1/pipeline/${encodeURIComponent(runId)}`));
}
