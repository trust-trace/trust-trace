import { proxyBackendJson } from '@/lib/backend-api';

export function GET() {
  return proxyBackendJson('/api/relations');
}
