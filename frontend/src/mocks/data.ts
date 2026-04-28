import {
  ARTICLES,
  COMPANIES,
  COMPANY_RELATIONS,
  type Company,
  type GraphResponse,
  type ReasoningTrace,
} from '@/lib/data';

const companiesById = new Map(COMPANIES.map((company) => [company.id, company]));

function getCompany(companyId: string): Company {
  const company = companiesById.get(companyId);
  if (!company) {
    throw new Error(`Missing mock company: ${companyId}`);
  }
  return company;
}

function companyNode(companyId: string, depth: number) {
  const company = getCompany(companyId);
  return {
    id: `company:${company.id}`,
    entityType: 'Company' as const,
    entityId: company.id,
    depth,
    label: company.name,
    data: {
      id: company.id,
      name: company.name,
      short: company.short,
      nip: company.nip,
      country: 'PL',
      score: company.score,
      trend: company.trend,
      risk: company.risk,
      history: company.history,
      keywords: company.keywords,
      articles: company.articles,
      lastUpdate: company.lastUpdate,
      sector: company.sector,
    },
  };
}

function fallbackGraph(companyId: string): GraphResponse {
  return {
    rootId: `company:${companyId}`,
    nodes: [companyNode(companyId, 0)],
    edges: [],
  };
}

const graphFixtures: Record<string, GraphResponse> = {
  jsw: {
    rootId: 'company:jsw',
    nodes: [
      companyNode('jsw', 0),
      companyNode('orlen', 1),
      companyNode('tauron', 2),
      {
        id: 'person:jan-kowalski',
        entityType: 'Person',
        entityId: 'jan-kowalski',
        depth: 1,
        label: 'Jan Kowalski',
        data: {
          name: 'Jan Kowalski',
          role: 'Board Member',
          description: 'Łączony z decyzjami zakupowymi i wewnętrznym audytem.',
          firmId: 'jsw',
          firmName: 'Jastrzębska Spółka Węglowa S.A.',
          eventCount: 2,
          trustScore: 32,
          risk: 'high',
        },
      },
      {
        id: 'person:anna-nowak',
        entityType: 'Person',
        entityId: 'anna-nowak',
        depth: 1,
        label: 'Anna Nowak',
        data: {
          name: 'Anna Nowak',
          role: 'Compliance Director',
          description: 'Koordynuje odpowiedzi spółki na publikacje i działania regulatora.',
          firmId: 'jsw',
          firmName: 'Jastrzębska Spółka Węglowa S.A.',
          eventCount: 1,
          trustScore: 44,
          risk: 'medium',
        },
      },
      {
        id: 'event:cba-investigation',
        entityType: 'Event',
        entityId: 'cba-investigation',
        depth: 1,
        label: 'CBA investigation update',
        data: {
          title: 'CBA investigation update',
          eventType: 'investigation',
          eventCategory: 'regulatory',
          riskLevel: 8,
          occurredAt: '2026-04-27T10:00:00',
          companyId: 'jsw',
          companyName: 'Jastrzębska Spółka Węglowa S.A.',
          excerpt: 'CBA przeprowadziło czynności w siedzibie spółki i zabezpieczyło dokumentację zakupową.',
          keywords: ['CBA', 'korupcja', 'audyt'],
          entities: ['JSW', 'CBA', 'Prokuratura'],
          source: 'Rzeczpospolita',
          sourceTitle: 'CBA wkroczyło do siedziby JSW',
          sourceUrl: 'https://example.com/jsw-cba',
        },
      },
      {
        id: 'event:labour-strike',
        entityType: 'Event',
        entityId: 'labour-strike',
        depth: 2,
        label: 'Labour strike escalation',
        data: {
          title: 'Labour strike escalation',
          eventType: 'labour',
          eventCategory: 'operations',
          riskLevel: 6,
          occurredAt: '2026-04-25T08:15:00',
          companyId: 'jsw',
          companyName: 'Jastrzębska Spółka Węglowa S.A.',
          excerpt: 'Związki zawodowe zapowiedziały eskalację protestu po zatrzymaniach w zarządzie.',
          keywords: ['strajk', 'związki', 'kopalnie'],
          entities: ['JSW', 'Solidarność'],
          source: 'TVN24 BiS',
          sourceTitle: 'Związki zawodowe zapowiadają strajk generalny',
          sourceUrl: 'https://example.com/jsw-strike',
        },
      },
    ],
    edges: [
      {
        id: 'company:jsw->person:jan-kowalski:AFFILIATED_WITH:-',
        source: 'company:jsw',
        target: 'person:jan-kowalski',
        relationshipType: 'AFFILIATED_WITH',
        connectionType: '',
        intensity: null,
        label: 'Affiliated with',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:jsw->person:anna-nowak:AFFILIATED_WITH:-',
        source: 'company:jsw',
        target: 'person:anna-nowak',
        relationshipType: 'AFFILIATED_WITH',
        connectionType: '',
        intensity: null,
        label: 'Affiliated with',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:jsw->event:cba-investigation:ABOUT:-',
        source: 'company:jsw',
        target: 'event:cba-investigation',
        relationshipType: 'ABOUT',
        connectionType: '',
        intensity: null,
        label: 'About',
        sourceUrl: 'https://example.com/jsw-cba',
        sourceTitle: 'CBA wkroczyło do siedziby JSW',
      },
      {
        id: 'person:jan-kowalski->event:cba-investigation:INVOLVED_IN:-',
        source: 'person:jan-kowalski',
        target: 'event:cba-investigation',
        relationshipType: 'INVOLVED_IN',
        connectionType: 'shared investigation subject',
        intensity: 0.74,
        label: 'Involved in',
        sourceUrl: 'https://example.com/jsw-cba',
        sourceTitle: 'CBA wkroczyło do siedziby JSW',
      },
      {
        id: 'person:anna-nowak->event:labour-strike:INVOLVED_IN:-',
        source: 'person:anna-nowak',
        target: 'event:labour-strike',
        relationshipType: 'INVOLVED_IN',
        connectionType: 'media response lead',
        intensity: 0.51,
        label: 'Involved in',
        sourceUrl: 'https://example.com/jsw-strike',
        sourceTitle: 'Związki zawodowe zapowiadają strajk generalny',
      },
      {
        id: 'company:jsw->company:orlen:CONNECTION:supply',
        source: 'company:jsw',
        target: 'company:orlen',
        relationshipType: 'CONNECTION',
        connectionType: 'energy supply dependency',
        intensity: 0.82,
        label: 'Connection',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:orlen->company:tauron:CONNECTION:grid',
        source: 'company:orlen',
        target: 'company:tauron',
        relationshipType: 'CONNECTION',
        connectionType: 'balancing agreement',
        intensity: 0.61,
        label: 'Connection',
        sourceUrl: '',
        sourceTitle: '',
      },
    ],
  },
  orlen: {
    rootId: 'company:orlen',
    nodes: [
      companyNode('orlen', 0),
      companyNode('lotos', 1),
      companyNode('tauron', 1),
      {
        id: 'person:maria-zielinska',
        entityType: 'Person',
        entityId: 'maria-zielinska',
        depth: 1,
        label: 'Maria Zielinska',
        data: {
          name: 'Maria Zielinska',
          role: 'Refinery Operations Lead',
          description: 'Nadzoruje ciągłość działania po serii publikacji o przestojach.',
          firmId: 'orlen',
          firmName: 'PKN Orlen S.A.',
          eventCount: 2,
          trustScore: 46,
          risk: 'medium',
        },
      },
      {
        id: 'event:refinery-outage',
        entityType: 'Event',
        entityId: 'refinery-outage',
        depth: 1,
        label: 'Refinery outage',
        data: {
          title: 'Refinery outage',
          eventType: 'operations',
          eventCategory: 'industrial',
          riskLevel: 7,
          occurredAt: '2026-04-24T06:45:00',
          companyId: 'orlen',
          companyName: 'PKN Orlen S.A.',
          excerpt: 'Przestój instalacji zwiększył presję na kontrakty dostaw w regionie.',
          keywords: ['rafineria', 'przestój', 'dostawy'],
          entities: ['Orlen', 'Lotos'],
          source: 'Puls Biznesu',
          sourceTitle: 'Problemy operacyjne w rafinerii Orlenu',
          sourceUrl: 'https://example.com/orlen-outage',
        },
      },
      {
        id: 'event:ukik-review',
        entityType: 'Event',
        entityId: 'ukik-review',
        depth: 1,
        label: 'UOKiK review',
        data: {
          title: 'UOKiK review',
          eventType: 'regulatory',
          eventCategory: 'compliance',
          riskLevel: 5,
          occurredAt: '2026-04-22T11:30:00',
          companyId: 'orlen',
          companyName: 'PKN Orlen S.A.',
          excerpt: 'Regulator analizuje skutki koncentracji i warunki umów logistycznych.',
          keywords: ['UOKiK', 'fuzja', 'logistyka'],
          entities: ['Orlen', 'Lotos', 'UOKiK'],
          source: 'Parkiet',
          sourceTitle: 'UOKiK przygląda się umowom logistycznym Orlenu',
          sourceUrl: 'https://example.com/orlen-uokik',
        },
      },
    ],
    edges: [
      {
        id: 'company:orlen->company:lotos:CONNECTION:integration',
        source: 'company:orlen',
        target: 'company:lotos',
        relationshipType: 'CONNECTION',
        connectionType: 'post-merger logistics',
        intensity: 0.87,
        label: 'Connection',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:orlen->company:tauron:CONNECTION:grid',
        source: 'company:orlen',
        target: 'company:tauron',
        relationshipType: 'CONNECTION',
        connectionType: 'energy balancing agreement',
        intensity: 0.62,
        label: 'Connection',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:orlen->person:maria-zielinska:AFFILIATED_WITH:-',
        source: 'company:orlen',
        target: 'person:maria-zielinska',
        relationshipType: 'AFFILIATED_WITH',
        connectionType: '',
        intensity: null,
        label: 'Affiliated with',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:orlen->event:refinery-outage:ABOUT:-',
        source: 'company:orlen',
        target: 'event:refinery-outage',
        relationshipType: 'ABOUT',
        connectionType: '',
        intensity: null,
        label: 'About',
        sourceUrl: 'https://example.com/orlen-outage',
        sourceTitle: 'Problemy operacyjne w rafinerii Orlenu',
      },
      {
        id: 'company:orlen->event:ukik-review:ABOUT:-',
        source: 'company:orlen',
        target: 'event:ukik-review',
        relationshipType: 'ABOUT',
        connectionType: '',
        intensity: null,
        label: 'About',
        sourceUrl: 'https://example.com/orlen-uokik',
        sourceTitle: 'UOKiK przygląda się umowom logistycznym Orlenu',
      },
      {
        id: 'person:maria-zielinska->event:refinery-outage:INVOLVED_IN:-',
        source: 'person:maria-zielinska',
        target: 'event:refinery-outage',
        relationshipType: 'INVOLVED_IN',
        connectionType: 'incident command',
        intensity: 0.68,
        label: 'Involved in',
        sourceUrl: 'https://example.com/orlen-outage',
        sourceTitle: 'Problemy operacyjne w rafinerii Orlenu',
      },
    ],
  },
  allegro: {
    rootId: 'company:allegro',
    nodes: [
      companyNode('allegro', 0),
      companyNode('lpp', 1),
      {
        id: 'person:ewa-mazur',
        entityType: 'Person',
        entityId: 'ewa-mazur',
        depth: 1,
        label: 'Ewa Mazur',
        data: {
          name: 'Ewa Mazur',
          role: 'Marketplace Strategy Lead',
          description: 'Łączy ekspansję marketplace z partnerami modowymi i reklamowymi.',
          firmId: 'allegro',
          firmName: 'Allegro.eu S.A.',
          eventCount: 2,
        },
      },
      {
        id: 'person:piotr-lewandowski',
        entityType: 'Person',
        entityId: 'piotr-lewandowski',
        depth: 1,
        label: 'Piotr Lewandowski',
        data: {
          name: 'Piotr Lewandowski',
          role: 'Board Adviser',
          description: 'Pojawia się w kilku relacjach właścicielskich i doradczych.',
          firmId: 'allegro',
          firmName: 'Allegro.eu S.A.',
          eventCount: 1,
        },
      },
      {
        id: 'event:campaign-launch',
        entityType: 'Event',
        entityId: 'campaign-launch',
        depth: 1,
        label: 'Regional campaign launch',
        data: {
          title: 'Regional campaign launch',
          eventType: 'commercial',
          eventCategory: 'growth',
          riskLevel: 3,
          occurredAt: '2026-04-20T09:00:00',
          companyId: 'allegro',
          companyName: 'Allegro.eu S.A.',
          excerpt: 'Kampania wspierająca ekspansję marketplace i nowe partnerstwa z markami detalicznymi.',
          keywords: ['kampania', 'marketplace', 'partnerstwo'],
          entities: ['Allegro', 'LPP'],
          source: 'Money.pl',
          sourceTitle: 'Allegro uruchamia regionalną kampanię partnerów',
          sourceUrl: 'https://example.com/allegro-campaign',
        },
      },
    ],
    edges: [
      {
        id: 'company:allegro->company:lpp:CONNECTION:marketplace',
        source: 'company:allegro',
        target: 'company:lpp',
        relationshipType: 'CONNECTION',
        connectionType: 'marketplace expansion',
        intensity: 0.73,
        label: 'Connection',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:allegro->person:ewa-mazur:AFFILIATED_WITH:-',
        source: 'company:allegro',
        target: 'person:ewa-mazur',
        relationshipType: 'AFFILIATED_WITH',
        connectionType: '',
        intensity: null,
        label: 'Affiliated with',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:allegro->person:piotr-lewandowski:AFFILIATED_WITH:-',
        source: 'company:allegro',
        target: 'person:piotr-lewandowski',
        relationshipType: 'AFFILIATED_WITH',
        connectionType: '',
        intensity: null,
        label: 'Affiliated with',
        sourceUrl: '',
        sourceTitle: '',
      },
      {
        id: 'company:allegro->event:campaign-launch:ABOUT:-',
        source: 'company:allegro',
        target: 'event:campaign-launch',
        relationshipType: 'ABOUT',
        connectionType: '',
        intensity: null,
        label: 'About',
        sourceUrl: 'https://example.com/allegro-campaign',
        sourceTitle: 'Allegro uruchamia regionalną kampanię partnerów',
      },
      {
        id: 'person:ewa-mazur->event:campaign-launch:INVOLVED_IN:-',
        source: 'person:ewa-mazur',
        target: 'event:campaign-launch',
        relationshipType: 'INVOLVED_IN',
        connectionType: 'campaign owner',
        intensity: 0.66,
        label: 'Involved in',
        sourceUrl: 'https://example.com/allegro-campaign',
        sourceTitle: 'Allegro uruchamia regionalną kampanię partnerów',
      },
    ],
  },
};

export const GRAPH_RESPONSES: Record<string, GraphResponse> = Object.fromEntries(
  COMPANIES.map((company) => [company.id, graphFixtures[company.id] ?? fallbackGraph(company.id)])
);

function deterministicFloat(seed: string, idx: number, min: number, max: number): number {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) & 0xffff;
  const t = ((h + idx * 7919) % 1000) / 1000;
  return +(min + t * (max - min)).toFixed(2);
}

function deterministicInt(seed: string, idx: number, min: number, max: number): number {
  return Math.floor(deterministicFloat(seed, idx, min, max + 0.99));
}

const REFERENCE_DATE = new Date('2026-04-27T12:00:00Z');

function makeEEMTrace(entityId: string, idx: number): ReasoningTrace {
  const eventTypes = ['fraud', 'regulatory', 'financial', 'labour', 'environmental'];
  const keywords = ['korupcja', 'zarząd', 'sankcje', 'restrukturyzacja', 'pranie pieniędzy', 'KNF', 'UOKiK'];
  const baseSentiment = deterministicFloat(entityId, idx, -0.95, 0.6);
  return {
    classifier_name: 'EEM',
    entity_type: 'event',
    entity_id: entityId,
    correlation_id: entityId,
    trace_data: {
      model_used: idx % 3 === 0 ? 'deterministic' : 'llm',
      fallback_reason: idx % 3 === 0 ? 'LLM timeout exceeded 2000ms' : null,
      sentiment_calculation: {
        base_sentiment: baseSentiment,
        event_type: eventTypes[idx % eventTypes.length],
        keyword_influences: keywords.slice(0, deterministicInt(entityId, idx + 10, 1, 4)),
        final_sentiment: +(baseSentiment * deterministicFloat(entityId, idx + 5, 0.8, 1.2)).toFixed(2),
      },
      impact_scoring: {
        baseline_impact: deterministicFloat(entityId, idx + 20, 1, 8),
        risk_level: deterministicInt(entityId, idx + 21, 1, 10),
        keyword_boost: deterministicFloat(entityId, idx + 22, 0, 2),
        final_impact: deterministicFloat(entityId, idx + 23, -8.5, 3),
      },
      source_tier_logic: {
        tier_assigned: ['tier-1', 'tier-2', 'tier-3'][idx % 3],
        authority_indicators: ['government source', 'verified journalist', 'official filing'].slice(0, (idx % 3) + 1),
        reasoning: 'Source matched authority keyword list and domain credibility database.',
      },
      keyword_extraction: {
        extracted_keywords: keywords.slice(0, 5),
        dedup_count: deterministicInt(entityId, idx + 30, 0, 3),
        top_6_keywords: keywords.slice(0, 6),
      },
    },
    created_at: new Date(REFERENCE_DATE.getTime() - idx * 3600000).toISOString(),
  };
}

function makeNSATrace(entityId: string, idx: number): ReasoningTrace {
  const rawScore = deterministicFloat(entityId, idx, 10, 90);
  return {
    classifier_name: 'NSA',
    entity_type: 'person',
    entity_id: entityId,
    correlation_id: null,
    trace_data: {
      evidence_summary: {
        total_evidence_count: deterministicInt(entityId, idx, 3, 15),
        evidence_by_source: { news: deterministicInt(entityId, idx + 1, 1, 8), registry: deterministicInt(entityId, idx + 2, 0, 4), filing: deterministicInt(entityId, idx + 3, 0, 3) },
        evidence_by_claim_type: { corruption: deterministicInt(entityId, idx + 4, 0, 5), fraud: deterministicInt(entityId, idx + 5, 0, 3), misconduct: deterministicInt(entityId, idx + 6, 0, 4) },
      },
      scoring_breakdown: Array.from({ length: 3 }, (_, i) => ({
        evidence_id: i + 1,
        source_kind: ['news', 'registry', 'filing'][i % 3],
        claim_type: ['corruption', 'fraud', 'misconduct'][i % 3],
        claim_weight: deterministicFloat(entityId, idx + i + 10, 0.3, 1.0),
        source_multiplier: deterministicFloat(entityId, idx + i + 13, 0.5, 2.0),
        severity: deterministicFloat(entityId, idx + i + 16, 0.1, 1.0),
        confidence: deterministicFloat(entityId, idx + i + 19, 0.4, 1.0),
        official_bonus: i === 1 ? 0.15 : 0,
        contribution_to_score: deterministicFloat(entityId, idx + i + 22, 2, 25),
      })),
      aggregation_logic: {
        raw_score: rawScore,
        clamped_score: Math.min(100, Math.max(0, rawScore)),
        news_only_cap_applied: rawScore > 70,
        news_only_cap_value: rawScore > 70 ? 70 : null,
      },
      person_context: {
        person_id: deterministicInt(entityId, idx + 40, 100, 999),
        person_name: entityId.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        role: ['Board Member', 'CFO', 'Compliance Director', 'CEO'][idx % 4],
        evidence_sources_hit: ['news', 'registry', 'filing'].slice(0, (idx % 3) + 1),
      },
    },
    created_at: new Date(REFERENCE_DATE.getTime() - idx * 7200000).toISOString(),
  };
}

function makeTarkovTrace(entityId: string, idx: number): ReasoningTrace {
  const eventTypes = ['investigation', 'labour', 'regulatory', 'financial', 'operations'];
  const keywordsSearched = ['CBA', 'korupcja', 'zatrzymanie', 'zarząd', 'prokuratura', 'śledztwo'];
  const baseConf = deterministicFloat(entityId, idx, 0.3, 0.9);
  return {
    classifier_name: 'Tarkov',
    entity_type: 'event_extraction',
    entity_id: entityId,
    correlation_id: entityId,
    trace_data: {
      extraction_method: idx % 2 === 0 ? 'keyword_based' : 'llm_based',
      keyword_matching: {
        event_type: eventTypes[idx % eventTypes.length],
        keywords_searched: keywordsSearched,
        keywords_found: keywordsSearched.slice(0, deterministicInt(entityId, idx + 5, 2, 6)),
        hit_sentences: [
          'CBA przeprowadziło akcję w siedzibie spółki.',
          'Zatrzymanym przedstawiono zarzuty korupcyjne.',
        ],
        deduped_hit_count: deterministicInt(entityId, idx + 8, 1, 4),
      },
      confidence_calculation: {
        base_confidence: baseConf,
        keyword_count: deterministicInt(entityId, idx + 10, 2, 8),
        keyword_boost: deterministicFloat(entityId, idx + 11, 0, 0.2),
        final_confidence: +(baseConf + deterministicFloat(entityId, idx + 12, 0, 0.15)).toFixed(2),
      },
      risk_level_assignment: {
        event_type: eventTypes[idx % eventTypes.length],
        baseline_risk: deterministicInt(entityId, idx + 15, 3, 8),
        keyword_count: deterministicInt(entityId, idx + 16, 2, 6),
        boost_value: deterministicFloat(entityId, idx + 17, 0, 2),
        final_risk_level: deterministicInt(entityId, idx + 18, 4, 10),
      },
      title_generation: {
        article_title: 'CBA wkroczyło do siedziby spółki',
        template_used: idx % 2 === 0 ? '{event_type}: {company}' : null,
        generated_title: 'Investigation — CBA action at company HQ',
      },
      source_reference: {
        url: 'https://example.com/article-' + entityId,
        source_title: 'Rzeczpospolita',
        credibility_score: deterministicFloat(entityId, idx + 20, 0.6, 1.0),
        language: 'pl',
        published_at: new Date(REFERENCE_DATE.getTime() - idx * 86400000).toISOString(),
      },
    },
    created_at: new Date(REFERENCE_DATE.getTime() - idx * 5400000).toISOString(),
  };
}

function makeMarketTrace(entityId: string, idx: number): ReasoningTrace {
  const exchanges = ['WSE', 'LSE', 'XETRA'];
  return {
    classifier_name: 'Market',
    entity_type: 'company',
    entity_id: entityId,
    correlation_id: null,
    trace_data: {
      ticker_search: {
        firm_name: entityId.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        search_strategy: (['exact', 'fuzzy', 'partial'] as const)[idx % 3],
        candidates_found: deterministicInt(entityId, idx, 1, 5),
        matching_process: Array.from({ length: 2 }, (_, i) => ({
          candidate_name: `Candidate ${i + 1}`,
          ticker: entityId.slice(0, 3).toUpperCase(),
          exchange: exchanges[i % exchanges.length],
          match_score: deterministicFloat(entityId, idx + i + 5, 0.5, 1.0),
          selected: i === 0,
          reason: i === 0 ? 'Highest match score' : 'Lower relevance',
        })),
      },
      listing_selection: {
        listings_considered: deterministicInt(entityId, idx + 10, 1, 4),
        selected_listings: [{
          tv_symbol: entityId.slice(0, 3).toUpperCase(),
          tv_exchange: 'WSE',
          ticker: entityId.slice(0, 3).toUpperCase(),
          exchange: 'WSE',
        }],
      },
      fetch_results: {
        listings_processed: 1,
        successful_fetches: 1,
        failed_fetches: 0,
        by_listing: [{
          tv_symbol: entityId.slice(0, 3).toUpperCase(),
          tv_exchange: 'WSE',
          bars_fetched: deterministicInt(entityId, idx + 15, 200, 365),
          bars_persisted: deterministicInt(entityId, idx + 16, 195, 365),
          data_completeness: deterministicFloat(entityId, idx + 17, 0.9, 1.0),
          error: null,
        }],
      },
      fetch_parameters: {
        n_bars_requested: 365,
        date_range: {
          start_date: '2025-04-27',
          end_date: '2026-04-27',
          days_back: 365,
        },
      },
    },
    created_at: new Date(REFERENCE_DATE.getTime() - idx * 10800000).toISOString(),
  };
}

export function generateMockTraces(entityId: string, classifier?: string): ReasoningTrace[] {
  const traces: ReasoningTrace[] = [];
  const generators: Record<string, (id: string, idx: number) => ReasoningTrace> = {
    EEM: makeEEMTrace,
    NSA: makeNSATrace,
    Tarkov: makeTarkovTrace,
    Market: makeMarketTrace,
  };

  if (classifier && generators[classifier]) {
    for (let i = 0; i < 3; i++) {
      traces.push(generators[classifier](entityId, i));
    }
  } else {
    for (const [, gen] of Object.entries(generators)) {
      for (let i = 0; i < 2; i++) {
        traces.push(gen(entityId, i));
      }
    }
  }

  return traces.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

export { ARTICLES, COMPANIES, COMPANY_RELATIONS };
