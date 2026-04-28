import { proxyBackend } from '@/lib/backend-api';

export async function POST(request: Request) {
  return proxyBackend('/v1/pipeline/run', {
    method: 'POST',
    body: await request.text(),
    headers: {
      'content-type': request.headers.get('content-type') ?? 'application/json',
    },
  });
}
