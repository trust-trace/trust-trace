function graphApiUrl(): string {
  const baseUrl = process.env.TARKOV_API_BASE_URL ?? 'http://127.0.0.1:8081';
  return `${baseUrl.replace(/\/$/, '')}/v1/graph`;
}

export async function GET() {
  const response = await fetch(graphApiUrl(), { cache: 'no-store' });

  if (!response.ok) {
    return Response.json({ detail: await response.text() }, { status: response.status });
  }

  return Response.json(await response.json());
}
