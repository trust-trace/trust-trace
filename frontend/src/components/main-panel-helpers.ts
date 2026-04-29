import type { Company, HistoryRangeKey } from '@/lib/data';

const FALLBACK_HISTORY_RANGE: HistoryRangeKey = '12M';

/** True when the company still has the backend placeholder score (scoring not finished). */
export function hasPendingScore(company: Company): boolean {
  if (company.lastUpdate) return false;
  if (company.keywords.length > 0) return false;
  if (company.score !== 50 || company.trend !== 0 || company.risk !== 'medium') return false;
  return (
    company.history.length === 1 &&
    company.history[0] === 50
  );
}

export function hasCompanyTradingView(company: Company): boolean {
  return Boolean(company.hasTradingView && company.tradingViewSymbol);
}

export function hasPendingScore(company: Company): boolean {
  return company.score === 0 && !company.lastUpdate;
}

export function getCompanyHistoryForRange(
  company: Company,
  activeRange: HistoryRangeKey
): number[] | null {
  const rangedHistory = company.historyByRange?.[activeRange];
  if (Array.isArray(rangedHistory) && rangedHistory.length > 0) {
    return rangedHistory;
  }

  const fallbackHistory = company.historyByRange?.[FALLBACK_HISTORY_RANGE];
  if (Array.isArray(fallbackHistory) && fallbackHistory.length > 0) {
    return fallbackHistory;
  }

  if (company.history.length > 1) return company.history;
  if (company.history.length === 1) return null;
  return [company.score];
}
