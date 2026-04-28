import type { Company, HistoryRangeKey } from '@/lib/data';

export function getCompanyHistoryForRange(
  company: Company,
  range: HistoryRangeKey
): number[] | null {
  const rangedHistory = company.historyByRange?.[range];
  if (rangedHistory && rangedHistory.length >= 2) {
    return rangedHistory;
  }

  if (range === '12M') {
    return company.history.length >= 2 ? company.history : null;
  }

  if (range === '6M') {
    return company.history.length >= 6 ? company.history.slice(-6) : null;
  }

  if (range === '3M') {
    return company.history.length >= 3 ? company.history.slice(-3) : null;
  }

  return null;
}

export function hasCompanyTradingView(company: Company): boolean {
  return Boolean(company.hasTradingView && company.tradingViewSymbol);
}
