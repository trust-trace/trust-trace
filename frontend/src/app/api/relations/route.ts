import { COMPANY_RELATIONS } from '@/lib/data';

export async function GET() {
  return Response.json(COMPANY_RELATIONS);
}
