const BACKEND_BASE_URL = process.env.TRUST_TRACE_BACKEND_URL ?? 'http://127.0.0.1:8081';

function toBackendUrl(pathname: string): URL {
  return new URL(pathname, BACKEND_BASE_URL.endsWith('/') ? BACKEND_BASE_URL : `${BACKEND_BASE_URL}/`);
}

export async function proxyBackendJson(pathname: string): Promise<Response> {
  const response = await fetch(toBackendUrl(pathname), {
    cache: 'no-store',
    headers: {
      accept: 'application/json',
    },
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
