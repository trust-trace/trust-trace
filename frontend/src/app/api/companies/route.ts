import { COMPANIES } from '@/lib/data';

export async function GET() {
  return Response.json(COMPANIES);
}
