import { describe, expect, it } from 'vitest';

import type { Company } from '@/lib/data';
import { getCompanyHistoryForRange, hasCompanyTradingView } from '@/components/main-panel-helpers';

const baseCompany: Company = {
  id: 'acme',
  name: 'Acme Holdings S.A.',
  short: 'Acme Holdings',
  nip: '1234567890',
  sector: 'Unknown',
  score: 82,
  trend: 4,
  risk: 'low',
  articles: 1,
  lastUpdate: '2026-04-27T11:00:00',
  history: [61, 64, 66],
  keywords: ['fraud'],
};

describe('main panel helpers', () => {
  it('uses range-specific backend history when present', () => {
    const company: Company = {
      ...baseCompany,
      historyByRange: {
        '12M': [61, 64, 66],
        '6M': [64, 66],
        '3M': [66],
        '30D': [66],
      },
    };

    expect(getCompanyHistoryForRange(company, '6M')).toEqual([64, 66]);
  });

  it('falls back to base history when range-specific history is missing', () => {
    expect(getCompanyHistoryForRange(baseCompany, '30D')).toEqual([61, 64, 66]);
  });

  it('reports tradingview availability only when backend fields are complete', () => {
    expect(
      hasCompanyTradingView({
        ...baseCompany,
        hasTradingView: true,
        tradingViewSymbol: 'NASDAQ:ACME',
      })
    ).toBe(true);

    expect(
      hasCompanyTradingView({
        ...baseCompany,
        hasTradingView: false,
        tradingViewSymbol: 'NASDAQ:ACME',
      })
    ).toBe(false);

    expect(
      hasCompanyTradingView({
        ...baseCompany,
        hasTradingView: true,
        tradingViewSymbol: '',
      })
    ).toBe(false);
  });
});
