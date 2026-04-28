function graphApiUrl(): string {
  const baseUrl = process.env.TARKOV_API_BASE_URL ?? 'http://127.0.0.1:8081';
  return `${baseUrl.replace(/\/$/, '')}/v1/graph`;
}

/**
 * Mock graph payload for development when backend is unavailable
 */
function getMockGraphPayload() {
  return {
    nodes: [
      {
        id: 'company:1',
        kind: 'company',
        label: 'PKN Orlen S.A.',
        properties: { company_id: 1, sector: 'Energetyka' },
      },
      {
        id: 'company:2',
        kind: 'company',
        label: 'Tauron S.A.',
        properties: { company_id: 2, sector: 'Energetyka' },
      },
      {
        id: 'person:1',
        kind: 'person',
        label: 'Jan Kowalski',
        properties: { person_id: 1 },
      },
      {
        id: 'person:2',
        kind: 'person',
        label: 'Maria Nowak',
        properties: { person_id: 2 },
      },
      {
        id: 'event:1',
        kind: 'event',
        label: 'Board Meeting',
        properties: { event_id: 1, date: '2026-04-20' },
      },
    ],
    edges: [
      {
        id: 'rel:1',
        source: 'company:1',
        target: 'person:1',
        type: 'AFFILIATED_WITH',
        properties: { role: 'CEO' },
      },
      {
        id: 'rel:2',
        source: 'company:2',
        target: 'person:2',
        type: 'AFFILIATED_WITH',
        properties: { role: 'CFO' },
      },
      {
        id: 'rel:3',
        source: 'company:1',
        target: 'company:2',
        type: 'INVOLVED_IN',
        properties: { relationship: 'joint_venture' },
      },
      {
        id: 'rel:4',
        source: 'person:1',
        target: 'event:1',
        type: 'PARTICIPATED_IN',
        properties: { attended: true },
      },
    ],
  };
}

export async function GET() {
  const response = await fetch(graphApiUrl(), { cache: 'no-store' }).catch(() => null);

  if (!response || !response.ok) {
    // Return mock data for development/demo purposes
    return Response.json(getMockGraphPayload());
  }

  return Response.json(await response.json());
}
