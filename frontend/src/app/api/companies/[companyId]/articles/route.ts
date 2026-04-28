import { ARTICLES } from '@/lib/data';

interface ArticlesRouteContext {
  params: Promise<{ companyId: string }>;
}

export async function GET(_: Request, context: ArticlesRouteContext) {
  const { companyId } = await context.params;

  return Response.json(ARTICLES[companyId] ?? []);
}
