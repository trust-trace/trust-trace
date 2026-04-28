import type { Company, HistoryRangeKey } from '@/lib/data';

const FALLBACK_HISTORY_RANGE: HistoryRangeKey = '12M';

export function hasCompanyTradingView(company: Company): boolean {
  return Boolean(company.hasTradingView && company.tradingViewSymbol);
}

export function getCompanyHistoryForRange(
  company: Company,
  activeRange: HistoryRangeKey
): number[] {
  const rangedHistory = company.historyByRange?.[activeRange];
  if (Array.isArray(rangedHistory) && rangedHistory.length > 0) {
    return rangedHistory;
  }

  const fallbackHistory = company.historyByRange?.[FALLBACK_HISTORY_RANGE];
  if (Array.isArray(fallbackHistory) && fallbackHistory.length > 0) {
    return fallbackHistory;
  }

  return company.history.length > 0 ? company.history : [company.score];
}
