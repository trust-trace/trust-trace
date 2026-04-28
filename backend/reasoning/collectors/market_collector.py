"""Reasoning trace collector for Market (Price & Listing Analysis)."""

from __future__ import annotations

from datetime import datetime
from reasoning.base import ReasoningTraceCollector, TraceCollectorRegistry
from reasoning.schemas import (
    MarketReasoningTrace,
    MarketTickerSearch,
    MarketTickerSearchCandidate,
    MarketListingSelection,
    MarketSelectedListing,
    MarketFetchResults,
    MarketFetchResultByListing,
    MarketFetchParameters,
    MarketDateRange,
)


@TraceCollectorRegistry.register("Market")
class MarketTraceCollector(ReasoningTraceCollector):
    """Collects reasoning traces during Market data fetching."""

    def __init__(self, firm_name: str, firm_id: int | None = None):
        """Initialize collector for market data fetch.
        
        Args:
            firm_name: Name of the firm
            firm_id: Optional ID of the firm
        """
        self.firm_name = firm_name
        self.firm_id = firm_id
        
        self.search_strategy: str | None = None
        self.ticker_candidates: list[MarketTickerSearchCandidate] = []
        self.selected_listings: list[MarketSelectedListing] = []
        self.fetch_results_list: list[MarketFetchResultByListing] = []
        
        self.n_bars_requested: int = 0
        self.start_date: datetime | None = None
        self.end_date: datetime | None = None
        self.days_back: int = 0

    def record_ticker_search(
        self,
        strategy: str,
        candidates: list[dict],
    ) -> None:
        """Record ticker search strategy and candidates.
        
        Args:
            strategy: Search strategy used ("exact", "fuzzy", "partial")
            candidates: List of candidate matches with name, ticker, exchange, match_score, selected, reason
        """
        self.search_strategy = strategy
        self.ticker_candidates = [
            MarketTickerSearchCandidate(
                candidate_name=c.get("name", ""),
                ticker=c.get("ticker", ""),
                exchange=c.get("exchange", ""),
                match_score=float(c.get("match_score", 0.0)),
                selected=c.get("selected", False),
                reason=c.get("reason", ""),
            )
            for c in candidates
        ]

    def record_listing_selected(
        self,
        tv_symbol: str,
        tv_exchange: str,
        ticker: str,
        exchange: str,
    ) -> None:
        """Record a selected listing.
        
        Args:
            tv_symbol: TradingView symbol
            tv_exchange: TradingView exchange
            ticker: Exchange ticker
            exchange: Exchange name
        """
        listing = MarketSelectedListing(
            tv_symbol=tv_symbol,
            tv_exchange=tv_exchange,
            ticker=ticker,
            exchange=exchange,
        )
        self.selected_listings.append(listing)

    def record_fetch_result(
        self,
        tv_symbol: str,
        tv_exchange: str,
        bars_fetched: int,
        bars_persisted: int,
        error: str | None = None,
    ) -> None:
        """Record fetch result for a specific listing.
        
        Args:
            tv_symbol: TradingView symbol
            tv_exchange: TradingView exchange
            bars_fetched: Number of bars fetched
            bars_persisted: Number of bars persisted to database
            error: Optional error message if fetch failed
        """
        data_completeness = (bars_persisted / bars_fetched * 100) if bars_fetched > 0 else 0.0
        
        result = MarketFetchResultByListing(
            tv_symbol=tv_symbol,
            tv_exchange=tv_exchange,
            bars_fetched=bars_fetched,
            bars_persisted=bars_persisted,
            data_completeness=data_completeness,
            error=error,
        )
        self.fetch_results_list.append(result)

    def record_fetch_parameters(
        self,
        n_bars_requested: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        days_back: int = 365,
    ) -> None:
        """Record fetch parameters used.
        
        Args:
            n_bars_requested: Number of bars requested
            start_date: Start date for fetch window
            end_date: End date for fetch window
            days_back: Number of days to look back
        """
        self.n_bars_requested = n_bars_requested
        self.start_date = start_date
        self.end_date = end_date
        self.days_back = days_back

    def collect(self) -> MarketReasoningTrace:
        """Collect and return the complete reasoning trace."""
        ticker_search = MarketTickerSearch(
            firm_name=self.firm_name,
            search_strategy=self.search_strategy or "exact",
            candidates_found=len(self.ticker_candidates),
            matching_process=self.ticker_candidates,
        )
        
        listing_selection = MarketListingSelection(
            listings_considered=len(self.selected_listings),
            selected_listings=self.selected_listings,
        )
        
        fetch_results = MarketFetchResults(
            listings_processed=len(self.fetch_results_list),
            successful_fetches=sum(1 for r in self.fetch_results_list if not r.error),
            failed_fetches=sum(1 for r in self.fetch_results_list if r.error),
            by_listing=self.fetch_results_list,
        )
        
        date_range = MarketDateRange(
            start_date=self.start_date,
            end_date=self.end_date,
            days_back=self.days_back,
        )
        
        fetch_parameters = MarketFetchParameters(
            n_bars_requested=self.n_bars_requested,
            date_range=date_range,
        )
        
        return MarketReasoningTrace(
            ticker_search=ticker_search,
            listing_selection=listing_selection,
            fetch_results=fetch_results,
            fetch_parameters=fetch_parameters,
        )
