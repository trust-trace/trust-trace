import { describe, expect, it } from 'vitest';

import type { Company } from '@/lib/data';
import {
  getCompanyHistoryForRange,
  hasCompanyTradingView,
  hasPendingScore,
} from './main-panel-helpers';

const baseCompany: Company = {
  id: 'test',
  name: 'Test S.A.',
  short: 'Test',
  nip: '1234567890',
  sector: 'Tech',
  score: 55,
  trend: 0,
  risk: 'medium',
  articles: 0,
  lastUpdate: '2026-04-28T10:00:00',
  history: [60, 58, 57, 56, 55, 54, 53, 52, 51, 52, 53, 55],
  keywords: [],
};

describe('main-panel-helpers', () => {
  it('treats one-point backend fallback history as unavailable', () => {
    const company: Company = { ...baseCompany, history: [55] };

    expect(getCompanyHistoryForRange(company, '12M')).toBeNull();
    expect(getCompanyHistoryForRange(company, '6M')).toBeNull();
    expect(getCompanyHistoryForRange(company, '30D')).toBeNull();
  });

  it('uses backend range hydration when available', () => {
    const company: Company = {
      ...baseCompany,
      historyByRange: {
        '12M': baseCompany.history,
        '6M': [53, 52, 51, 52, 53, 55],
        '3M': [52, 53, 55],
        '30D': [51, 52, 53, 55],
      },
    };

    expect(getCompanyHistoryForRange(company, '6M')).toEqual([53, 52, 51, 52, 53, 55]);
    expect(getCompanyHistoryForRange(company, '30D')).toEqual([51, 52, 53, 55]);
  });

  it('requires both tradingview flag and symbol', () => {
    expect(hasCompanyTradingView(baseCompany)).toBe(false);
    expect(
      hasCompanyTradingView({ ...baseCompany, hasTradingView: true, tradingViewSymbol: 'GPW:TST' })
    ).toBe(true);
  });

  it('detects the backend placeholder score payload as pending', () => {
    expect(
      hasPendingScore({
        ...baseCompany,
        score: 50,
        trend: 0,
        risk: 'medium',
        history: [50],
        keywords: [],
        lastUpdate: '',
      })
    ).toBe(true);

    expect(
      hasPendingScore({
        ...baseCompany,
        score: 50,
        trend: 0,
        risk: 'medium',
        history: [50],
        keywords: ['audit'],
        lastUpdate: '',
      })
    ).toBe(false);
  });
});
