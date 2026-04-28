const BACKEND_BASE_URL = process.env.TRUST_TRACE_BACKEND_URL ?? 'http://127.0.0.1:8081';

function toBackendUrl(pathname: string): URL {
  return new URL(pathname, BACKEND_BASE_URL.endsWith('/') ? BACKEND_BASE_URL : `${BACKEND_BASE_URL}/`);
}

export async function proxyBackend(pathname: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);

  if (!headers.has('accept')) {
    headers.set('accept', 'application/json');
  }

  const response = await fetch(toBackendUrl(pathname), {
    ...init,
    cache: 'no-store',
    headers,
  });

  const body = await response.text();

  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/json; charset=utf-8',
    },
  });
}

export async function proxyBackendJson(pathname: string): Promise<Response> {
  return proxyBackend(pathname);
}
