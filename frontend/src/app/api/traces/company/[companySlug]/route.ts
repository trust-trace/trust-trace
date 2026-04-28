import { proxyBackendJson } from '@/lib/backend-api';

export function GET(
  _request: Request,
  { params }: { params: Promise<{ companySlug: string }> }
) {
  return params.then(({ companySlug }) =>
    proxyBackendJson(
      `/api/v1/traces/company/${encodeURIComponent(companySlug)}`
    )
  );
}
