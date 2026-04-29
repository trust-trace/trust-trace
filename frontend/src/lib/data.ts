export type Risk = 'high' | 'medium' | 'low';
export type SourceTier = 'tier-1' | 'tier-2' | 'tier-3';
export type GraphRelationType = 'person' | 'partnership' | 'business';
export type HistoryRangeKey = '12M' | '6M' | '3M' | '30D';

export type CompanyHistoryByRange = Record<HistoryRangeKey, number[]>;

export interface Company {
  id: string;
  name: string;
  short: string;
  nip: string;
  sector: string;
  score: number;
  trend: number;
  risk: Risk;
  articles: number;
  lastUpdate: string;
  history: number[];
  historyByRange?: Partial<CompanyHistoryByRange>;
  keywords: string[];
  tradingViewSymbol?: string;
  hasTradingView?: boolean;
}

export interface Article {
  id: string;
  headline: string;
  source: string;
  sourceUrl?: string;
  sourceTier: SourceTier;
  date: string;
  sentiment: number;
  impact: number;
  keywords: string[];
  excerpt: string;
  entities: string[];
  /** Quote / span of text from the source used for extraction and scoring (full transparency). */
  sourceText?: string;
  /** All persisted source rows for this event (URLs, categories, credibility). */
  sources?: ArticleSourceRef[];
  /** Reasoning traces linked to this article/event (e.g. EEM impact breakdown). */
  traces?: ReasoningTrace[];
}

/** One stored source row attached to the pipeline event behind an article. */
export interface ArticleSourceRef {
  url: string;
  title: string | null;
  sourceCategory: string;
  publishedAt: string | null;
  credibility: number | null;
}

export interface CompanyRelation {
  sourceCompanyId: string;
  targetCompanyId: string;
  type: GraphRelationType;
  label?: string;
}

export type GraphEntityType = 'Company' | 'Person' | 'Event';
export type GraphRelationshipType =
  | 'CONNECTION'
  | 'ABOUT'
  | 'INVOLVED_IN'
  | 'AFFILIATED_WITH';

export interface GraphNodeBase<
  TType extends GraphEntityType,
  TData extends object,
> {
  id: string;
  entityType: TType;
  entityId: string;
  depth: number;
  label: string;
  data: TData;
}

export interface CompanyGraphNodeData {
  id?: string;
  name?: string;
  short?: string;
  nip?: string;
  sector?: string;
  country?: string;
  score?: number;
  trend?: number;
  risk?: Risk;
  history?: number[];
  keywords?: string[];
  articles?: number;
  lastUpdate?: string;
}

export interface PersonGraphNodeData {
  name?: string;
  role?: string;
  description?: string;
  firmId?: string;
  firmName?: string;
  eventCount?: number;
  trustScore?: number;
  risk?: Risk;
}

export interface EventGraphNodeData {
  title?: string;
  eventType?: string;
  eventCategory?: string;
  riskLevel?: number;
  risk?: Risk;
  occurredAt?: string;
  companyId?: string;
  companyName?: string;
  excerpt?: string;
  keywords?: string[];
  entities?: string[];
  source?: string;
  sourceTitle?: string;
  sourceUrl?: string;
}

export type CompanyGraphNode = GraphNodeBase<'Company', CompanyGraphNodeData>;
export type PersonGraphNode = GraphNodeBase<'Person', PersonGraphNodeData>;
export type EventGraphNode = GraphNodeBase<'Event', EventGraphNodeData>;

export type GraphNode = CompanyGraphNode | PersonGraphNode | EventGraphNode;

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationshipType: GraphRelationshipType;
  connectionType: string;
  intensity: number | null;
  label: string;
  sourceUrl: string;
  sourceTitle: string;
}

export interface GraphResponse {
  rootId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Article ingestion worker: `queued` is pending/retrying; `parsing` is in-flight. */
export interface IngestionStats {
  parsing: number;
  queued: number;
}

export interface PipelineRunAccepted {
  status: string;
  run_id: string;
}

export interface PipelineRunStatus {
  run_id: string;
  query: string;
  status: string;
  phase: string;
  article_target: number;
  articles_scraped: number;
  articles_processed: number;
  firm_ids: string[];
  final_scores: Record<string, number>;
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface ReasoningTrace {
  classifier_name: 'EEM' | 'NSA' | 'Tarkov' | 'Market';
  entity_type: string;
  entity_id: string;
  correlation_id: string | null;
  trace_data: Record<string, unknown>;
  created_at: string;
}

export const COMPANIES: Company[] = [
  {
    id: 'orlen',
    name: 'PKN Orlen S.A.',
    short: 'Orlen',
    nip: '7740001454',
    sector: 'Energetyka',
    score: 72,
    trend: -4,
    risk: 'medium',
    articles: 47,
    lastUpdate: '2026-04-26T14:32:00',
    history: [78, 80, 79, 76, 74, 75, 77, 76, 73, 72, 76, 72],
    keywords: ['zarząd', 'restrukturyzacja', 'sankcje', 'inwestycje'],
  },
  {
    id: 'cdpr',
    name: 'CD Projekt S.A.',
    short: 'CD Projekt',
    nip: '7342867148',
    sector: 'Gaming / IT',
    score: 88,
    trend: 3,
    risk: 'low',
    articles: 23,
    lastUpdate: '2026-04-27T09:11:00',
    history: [82, 83, 81, 84, 85, 86, 84, 85, 87, 86, 85, 88],
    keywords: ['premiera', 'wyniki finansowe', 'akcjonariusze'],
  },
  {
    id: 'jsw',
    name: 'Jastrzębska Spółka Węglowa S.A.',
    short: 'JSW',
    nip: '6332160109',
    sector: 'Górnictwo',
    score: 41,
    trend: -12,
    risk: 'high',
    articles: 89,
    lastUpdate: '2026-04-27T07:48:00',
    history: [62, 60, 58, 55, 53, 54, 51, 49, 47, 45, 43, 41],
    keywords: ['zarzuty', 'CBA', 'korupcja', 'zarząd', 'śledztwo'],
  },
  {
    id: 'kghm',
    name: 'KGHM Polska Miedź S.A.',
    short: 'KGHM',
    nip: '6920000013',
    sector: 'Wydobywczy',
    score: 79,
    trend: 1,
    risk: 'low',
    articles: 34,
    lastUpdate: '2026-04-26T18:22:00',
    history: [76, 77, 78, 77, 79, 78, 80, 79, 78, 79, 78, 79],
    keywords: ['eksport', 'umowy', 'inwestycje zagraniczne'],
  },
  {
    id: 'allegro',
    name: 'Allegro.eu S.A.',
    short: 'Allegro',
    nip: '5252674798',
    sector: 'E-commerce',
    score: 84,
    trend: 2,
    risk: 'low',
    articles: 31,
    lastUpdate: '2026-04-27T11:03:00',
    history: [80, 81, 82, 81, 83, 82, 83, 84, 83, 84, 83, 84],
    keywords: ['ekspansja', 'akwizycja', 'wyniki kwartalne'],
  },
  {
    id: 'pzu',
    name: 'Powszechny Zakład Ubezpieczeń S.A.',
    short: 'PZU',
    nip: '5260250995',
    sector: 'Ubezpieczenia',
    score: 76,
    trend: -2,
    risk: 'medium',
    articles: 28,
    lastUpdate: '2026-04-26T16:14:00',
    history: [80, 79, 78, 79, 77, 78, 77, 76, 77, 76, 77, 76],
    keywords: ['regulator', 'KNF', 'fuzja'],
  },
  {
    id: 'lotos',
    name: 'Grupa Lotos S.A.',
    short: 'Lotos',
    nip: '5830000960',
    sector: 'Energetyka',
    score: 58,
    trend: -7,
    risk: 'medium',
    articles: 52,
    lastUpdate: '2026-04-27T08:30:00',
    history: [70, 68, 67, 65, 64, 63, 62, 60, 61, 59, 60, 58],
    keywords: ['fuzja', 'antymonopolowy', 'UOKiK', 'zarzuty'],
  },
  {
    id: 'pko',
    name: 'PKO Bank Polski S.A.',
    short: 'PKO BP',
    nip: '5250007738',
    sector: 'Bankowość',
    score: 81,
    trend: 1,
    risk: 'low',
    articles: 41,
    lastUpdate: '2026-04-27T10:45:00',
    history: [78, 79, 80, 79, 80, 81, 80, 81, 80, 81, 80, 81],
    keywords: ['kredyty', 'wyniki', 'CHF', 'ugody'],
  },
  {
    id: 'tauron',
    name: 'Tauron Polska Energia S.A.',
    short: 'Tauron',
    nip: '9542583988',
    sector: 'Energetyka',
    score: 64,
    trend: -3,
    risk: 'medium',
    articles: 38,
    lastUpdate: '2026-04-26T22:01:00',
    history: [70, 69, 68, 67, 68, 66, 67, 65, 66, 65, 65, 64],
    keywords: ['transformacja', 'węgiel', 'OZE'],
  },
  {
    id: 'getin',
    name: 'Getin Holding S.A.',
    short: 'Getin',
    nip: '8951558992',
    sector: 'Finanse',
    score: 22,
    trend: -18,
    risk: 'high',
    articles: 134,
    lastUpdate: '2026-04-27T12:20:00',
    history: [55, 50, 46, 42, 40, 38, 35, 32, 30, 28, 25, 22],
    keywords: ['upadłość', 'pranie pieniędzy', 'zarzuty', 'KNF', 'śledztwo', 'oszustwo'],
  },
  {
    id: 'mbank',
    name: 'mBank S.A.',
    short: 'mBank',
    nip: '5260215088',
    sector: 'Bankowość',
    score: 78,
    trend: 0,
    risk: 'low',
    articles: 26,
    lastUpdate: '2026-04-27T06:55:00',
    history: [78, 77, 78, 79, 78, 78, 77, 78, 79, 78, 78, 78],
    keywords: ['CHF', 'wyniki', 'cyfryzacja'],
  },
  {
    id: 'cyfrowy',
    name: 'Cyfrowy Polsat S.A.',
    short: 'Cyfrowy Polsat',
    nip: '7961810732',
    sector: 'Telekomunikacja',
    score: 69,
    trend: -1,
    risk: 'medium',
    articles: 22,
    lastUpdate: '2026-04-26T19:40:00',
    history: [72, 71, 70, 71, 70, 69, 70, 69, 70, 69, 70, 69],
    keywords: ['Plus', '5G', 'akwizycja'],
  },
  {
    id: 'lpp',
    name: 'LPP S.A.',
    short: 'LPP',
    nip: '5830048113',
    sector: 'Retail',
    score: 53,
    trend: -9,
    risk: 'medium',
    articles: 67,
    lastUpdate: '2026-04-27T13:15:00',
    history: [68, 66, 65, 63, 62, 60, 58, 57, 55, 54, 53, 53],
    keywords: ['Rosja', 'sankcje', 'reorganizacja', 'zarzuty'],
  },
  {
    id: 'asseco',
    name: 'Asseco Poland S.A.',
    short: 'Asseco',
    nip: '5220003557',
    sector: 'IT',
    score: 82,
    trend: 2,
    risk: 'low',
    articles: 19,
    lastUpdate: '2026-04-27T05:22:00',
    history: [78, 79, 80, 80, 81, 80, 81, 82, 81, 82, 81, 82],
    keywords: ['kontrakty', 'sektor publiczny', 'eksport'],
  },
  {
    id: 'dino',
    name: 'Dino Polska S.A.',
    short: 'Dino',
    nip: '6151000549',
    sector: 'Retail',
    score: 87,
    trend: 1,
    risk: 'low',
    articles: 17,
    lastUpdate: '2026-04-26T20:10:00',
    history: [84, 85, 86, 85, 86, 87, 86, 87, 86, 87, 86, 87],
    keywords: ['ekspansja', 'wyniki', 'sklepy'],
  },
];

const JSW_ARTICLES: Article[] = [
  {
    id: 'a1',
    headline: 'CBA wkroczyło do siedziby JSW. Zatrzymano trzech członków zarządu',
    source: 'Rzeczpospolita',
    sourceTier: 'tier-1',
    date: '2026-04-26T08:14:00',
    sentiment: -0.92,
    impact: -8.4,
    keywords: ['CBA', 'zatrzymanie', 'zarząd', 'korupcja'],
    excerpt:
      'Funkcjonariusze CBA przeprowadzili w czwartek rano akcję w siedzibie spółki w Jastrzębiu-Zdroju. Zatrzymanym przedstawiono zarzuty przyjęcia korzyści majątkowej w łącznej kwocie ponad 4,2 mln zł oraz działania na szkodę spółki Skarbu Państwa.',
    entities: ['CBA', 'Prokuratura Regionalna w Katowicach', 'JSW S.A.'],
    sourceText:
      'Funkcjonariusze CBA przeprowadzili w czwartek rano akcję w siedzibie spółki w Jastrzębiu-Zdroju.',
    sources: [
      {
        url: 'https://example.com/articles/jsw-cba',
        title: 'CBA wkroczyło do siedziby JSW',
        sourceCategory: 'article',
        publishedAt: '2026-04-26T08:00:00',
        credibility: 0.92,
      },
    ],
    traces: [
      {
        classifier_name: 'EEM',
        entity_type: 'event',
        entity_id: 'a1',
        correlation_id: null,
        trace_data: {
          model_used: 'llm',
          impact_scoring: {
            baseline_impact: -6.2,
            risk_level: 9,
            keyword_boost: -2.2,
            final_impact: -8.4,
          },
          sentiment_calculation: {
            base_sentiment: -0.85,
            event_type: 'investigation',
            keyword_influences: ['CBA', 'zarzuty'],
            final_sentiment: -0.92,
          },
        },
        created_at: '2026-04-26T08:15:00',
      },
    ],
  },
  {
    id: 'a2',
    headline: 'Akcjonariusze JSW domagają się zwołania nadzwyczajnego walnego zgromadzenia',
    source: 'Parkiet',
    sourceTier: 'tier-1',
    date: '2026-04-25T17:22:00',
    sentiment: -0.41,
    impact: -2.1,
    keywords: ['akcjonariusze', 'NWZ', 'zarząd'],
    excerpt:
      'Grupa akcjonariuszy reprezentujących łącznie 12,3% kapitału zakładowego złożyła wniosek o niezwłoczne zwołanie nadzwyczajnego walnego zgromadzenia. W porządku obrad — odwołanie obecnych członków rady nadzorczej.',
    entities: ['Rada Nadzorcza JSW', 'Komisja Nadzoru Finansowego'],
  },
  {
    id: 'a3',
    headline: 'JSW publikuje wstępne wyniki Q1 — przychody w dół o 18%',
    source: 'Bankier.pl',
    sourceTier: 'tier-2',
    date: '2026-04-24T11:00:00',
    sentiment: -0.32,
    impact: -1.4,
    keywords: ['wyniki', 'przychody', 'kwartał'],
    excerpt:
      'Spółka opublikowała wstępne, niezaudytowane szacunki za I kwartał 2026. Przychody na poziomie 2,8 mld zł — spadek o 18% rok do roku. EBITDA niższa o 31%.',
    entities: ['Zarząd JSW'],
  },
  {
    id: 'a4',
    headline: 'Związki zawodowe zapowiadają strajk generalny w kopalniach JSW',
    source: 'TVN24 BiS',
    sourceTier: 'tier-2',
    date: '2026-04-23T14:55:00',
    sentiment: -0.55,
    impact: -2.8,
    keywords: ['strajk', 'związki zawodowe', 'kopalnie'],
    excerpt:
      'Solidarność oraz WZZ "Sierpień 80" ogłosiły wspólne stanowisko w sprawie podwyżek i rozliczenia byłego zarządu. Strajk generalny zapowiedziany na 6 maja.',
    entities: ['NSZZ Solidarność', 'WZZ Sierpień 80'],
  },
  {
    id: 'a5',
    headline: 'Skarb Państwa rozważa interwencję kapitałową w JSW',
    source: 'Puls Biznesu',
    sourceTier: 'tier-1',
    date: '2026-04-22T09:30:00',
    sentiment: 0.21,
    impact: 0.8,
    keywords: ['Skarb Państwa', 'kapitał', 'wsparcie'],
    excerpt:
      'Według nieoficjalnych informacji Ministerstwo Aktywów Państwowych przygotowuje pakiet wsparcia kapitałowego dla spółki. Decyzja zapadnie w najbliższych dwóch tygodniach.',
    entities: ['Ministerstwo Aktywów Państwowych', 'Skarb Państwa'],
  },
  {
    id: 'a6',
    headline: 'Prokuratura: zarzuty wobec byłego prezesa JSW dotyczą lat 2022–2024',
    source: 'Onet Biznes',
    sourceTier: 'tier-2',
    date: '2026-04-21T16:18:00',
    sentiment: -0.78,
    impact: -3.6,
    keywords: ['prokuratura', 'zarzuty', 'były prezes'],
    excerpt:
      'Prokuratura Regionalna w Katowicach poinformowała o szczegółach zarzutów. Mowa o niegospodarności wielkich rozmiarów oraz przyjmowaniu korzyści majątkowych przez okres dwóch lat.',
    entities: ['Prokuratura Regionalna w Katowicach'],
  },
  {
    id: 'a7',
    headline: 'Notowania JSW spadły o 14% w ciągu tygodnia',
    source: 'Stooq',
    sourceTier: 'tier-3',
    date: '2026-04-20T17:45:00',
    sentiment: -0.48,
    impact: -2.2,
    keywords: ['giełda', 'kurs', 'spadek'],
    excerpt:
      'W ciągu ostatnich pięciu sesji kurs akcji spółki obniżył się z poziomu 38,40 zł do 33,02 zł. Wolumen obrotu o 240% wyższy od średniej z ostatnich 30 sesji.',
    entities: ['GPW'],
  },
  {
    id: 'a8',
    headline: 'JSW podpisała list intencyjny ws. modernizacji infrastruktury wydobywczej',
    source: 'Money.pl',
    sourceTier: 'tier-3',
    date: '2026-04-18T10:12:00',
    sentiment: 0.45,
    impact: 1.1,
    keywords: ['inwestycje', 'modernizacja', 'kontrakt'],
    excerpt:
      'Spółka podpisała wstępne porozumienie z konsorcjum dostawców na modernizację systemów wentylacji i transportu w trzech kopalniach. Wartość projektu — szacunkowo 380 mln zł.',
    entities: ['Konsorcjum FAMUR-Kopex'],
  },
];

type ArticleTemplate = { h: string; s: number; i: number; k: string[] };

const TEMPLATES: Record<Risk, ArticleTemplate[]> = {
  low: [
    { h: '{short} publikuje rekordowe wyniki kwartalne', s: 0.72, i: 2.4, k: ['wyniki', 'przychody'] },
    { h: 'Analitycy podnoszą rekomendacje dla {short}', s: 0.58, i: 1.8, k: ['rekomendacje', 'analitycy'] },
    { h: '{short} ogłasza nowy program inwestycyjny', s: 0.61, i: 2.0, k: ['inwestycje', 'rozwój'] },
    { h: 'Walne zgromadzenie {short} zatwierdziło dywidendę', s: 0.42, i: 1.1, k: ['dywidenda', 'WZA'] },
  ],
  medium: [
    { h: '{short} odnotowuje spadek przychodów rok do roku', s: -0.38, i: -1.6, k: ['wyniki', 'spadek'] },
    { h: 'UOKiK wszczyna postępowanie wyjaśniające wobec {short}', s: -0.62, i: -3.1, k: ['UOKiK', 'postępowanie'] },
    { h: 'Restrukturyzacja zarządu w {short}', s: -0.21, i: -0.9, k: ['zarząd', 'restrukturyzacja'] },
    { h: '{short} komentuje doniesienia medialne', s: -0.18, i: -0.4, k: ['oświadczenie', 'media'] },
  ],
  high: [
    { h: 'Zarzuty korupcyjne wobec członków zarządu {short}', s: -0.88, i: -7.2, k: ['zarzuty', 'korupcja', 'zarząd'] },
    { h: 'KNF nakłada karę na {short}', s: -0.71, i: -4.4, k: ['KNF', 'kara', 'sankcje'] },
    { h: 'Śledztwo prokuratorskie w sprawie {short}', s: -0.79, i: -5.1, k: ['prokuratura', 'śledztwo'] },
    { h: 'Pranie pieniędzy — nowe ustalenia dot. {short}', s: -0.91, i: -6.8, k: ['pranie pieniędzy', 'AML'] },
  ],
};

const SOURCES = ['Rzeczpospolita', 'Parkiet', 'Puls Biznesu', 'Bankier.pl', 'Onet Biznes', 'Money.pl', 'TVN24 BiS', 'Wyborcza Biznes'] as const;
const SOURCE_TIERS: Record<string, SourceTier> = {
  Rzeczpospolita: 'tier-1',
  Parkiet: 'tier-1',
  'Puls Biznesu': 'tier-1',
  'Wyborcza Biznes': 'tier-1',
  'Bankier.pl': 'tier-2',
  'Onet Biznes': 'tier-2',
  'TVN24 BiS': 'tier-2',
  'Money.pl': 'tier-3',
};

export const COMPANY_RELATIONS: CompanyRelation[] = [
  {
    sourceCompanyId: 'allegro',
    targetCompanyId: 'cyfrowy',
    type: 'business',
    label: 'Cross-channel distribution',
  },
  {
    sourceCompanyId: 'allegro',
    targetCompanyId: 'dino',
    type: 'partnership',
    label: 'Marketplace expansion partnership',
  },
  {
    sourceCompanyId: 'allegro',
    targetCompanyId: 'lpp',
    type: 'person',
    label: 'Shared supervisory board adviser',
  },
  {
    sourceCompanyId: 'cyfrowy',
    targetCompanyId: 'pko',
    type: 'business',
    label: 'Payments and settlement integration',
  },
  {
    sourceCompanyId: 'dino',
    targetCompanyId: 'asseco',
    type: 'business',
    label: 'Retail systems rollout',
  },
  {
    sourceCompanyId: 'lpp',
    targetCompanyId: 'orlen',
    type: 'partnership',
    label: 'Logistics fuel agreement',
  },
  {
    sourceCompanyId: 'orlen',
    targetCompanyId: 'tauron',
    type: 'business',
    label: 'Energy balancing agreement',
  },
  {
    sourceCompanyId: 'pko',
    targetCompanyId: 'mbank',
    type: 'person',
    label: 'Former executive overlap',
  },
];

// Deterministic "jitter" based on company id and article index — no Math.random()
// so SSR and client produce identical output (no hydration mismatch).
function deterministicSentimentOffset(companyId: string, idx: number): number {
  let hash = 0;
  for (const ch of companyId) hash = (hash * 31 + ch.charCodeAt(0)) & 0xffff;
  // Range: -0.05 .. +0.05
  return ((hash + idx * 7919) % 101) / 1000 - 0.05;
}

// Fixed reference date so dates don't shift between SSR and client.
const REFERENCE_DATE = new Date('2026-04-27T12:00:00Z');

function generateArticles(company: Company): Article[] {
  const pool = TEMPLATES[company.risk];
  const out: Article[] = [];
  for (let i = 0; i < 6; i++) {
    const t = pool[i % pool.length];
    const src = SOURCES[i % SOURCES.length];
    // Deterministic spacing: 1, 2.5, 4, 5.5, 7, 8.5 days ago
    const daysAgo = (i + 1) * 1.5;
    const date = new Date(REFERENCE_DATE.getTime() - daysAgo * 86400000);
    out.push({
      id: `${company.id}-a${i}`,
      headline: t.h.replace('{short}', company.short),
      source: src,
      sourceTier: SOURCE_TIERS[src],
      date: date.toISOString(),
      sentiment: t.s + deterministicSentimentOffset(company.id, i),
      impact: t.i,
      keywords: t.k,
      excerpt:
        'Treść artykułu została zagregowana z publicznie dostępnych źródeł i poddana analizie sentymentu w kontekście branżowym. Algorytm uwzględnia fleksję, synonimy oraz kontekst wystąpień słów kluczowych ryzyka.',
      entities: [company.name],
      sourceText: `Fragment tekstu użytego w scoringu (symulacja): ${company.short} — ${t.k.join(', ')}.`,
      sources: [
        {
          url: `https://example.com/articles/${company.id}-${i}`,
          title: t.h.replace('{short}', company.short),
          sourceCategory: 'article',
          publishedAt: date.toISOString(),
          credibility:
            Math.round((0.55 + ((company.id.charCodeAt(0) + i * 31) % 35) / 100) * 100) /
            100,
        },
      ],
      traces: [],
    });
  }
  return out;
}

export const ARTICLES: Record<string, Article[]> = {
  jsw: JSW_ARTICLES,
};

for (const company of COMPANIES) {
  if (!ARTICLES[company.id]) {
    ARTICLES[company.id] = generateArticles(company);
  }
}
