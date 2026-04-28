"""Company matching: DB-backed heuristics + LLM discovery."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from tarkov.database.models import Firm
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.llm.client import LLMClient
from tarkov.utils.logger import get_logger
from tarkov.utils.text_utils import normalize_whitespace

logger = get_logger(__name__)


_DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_DATACLASS_KWARGS)
class MatchedCompany:
    company_name: str
    ticker: str | None
    confidence: float
    matched_text: str


class CompanyMatcher:
    def __init__(
        self,
        db_session: Session,
        llm_client: LLMClient | None = None,
    ):
        self.db_session = db_session
        self.firm_repo = FirmRepository(db_session)
        self.llm_client = llm_client

    def _load_candidates_from_db(self) -> list[dict]:
        """Build the candidate list from firm + firm_alias tables."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        firms = (
            self.db_session.execute(
                select(Firm).options(selectinload(Firm.aliases))
            )
            .scalars()
            .all()
        )

        candidates: list[dict] = []
        for firm in firms:
            aliases = [a.alias for a in firm.aliases if a.alias]
            if firm.full_name and firm.full_name not in aliases:
                aliases.append(firm.full_name)
            candidates.append(
                {
                    "name": firm.full_name,
                    "ticker": firm.market_ticker,
                    "aliases": aliases,
                }
            )
        return candidates

    def match_companies(self, article_text: str) -> list[MatchedCompany]:
        text = normalize_whitespace(article_text)
        lowered = text.lower()

        candidates = self._load_candidates_from_db()
        logger.info("Loaded %d firm candidates from DB", len(candidates))
        heuristic_matches = self._match_heuristic(text, lowered, candidates)

        if self.llm_client and self.llm_client.has_api_key and heuristic_matches:
            llm_matches = self._match_llm(text, heuristic_matches)
            if llm_matches:
                return llm_matches

        if heuristic_matches:
            return heuristic_matches

        has_llm = bool(self.llm_client and self.llm_client.has_api_key)
        logger.info(
            "No heuristic matches — LLM discovery %s (provider=%s, has_key=%s)",
            "enabled" if has_llm else "DISABLED",
            getattr(self.llm_client, "provider", "N/A") if self.llm_client else "N/A",
            has_llm,
        )

        if has_llm:
            return self._discover_companies_llm(text)

        return []

    def _match_heuristic(
        self, text: str, lowered: str, candidates: list[dict]
    ) -> list[MatchedCompany]:
        results: list[MatchedCompany] = []
        seen: set[tuple[str, str | None]] = set()

        for row in candidates:
            name = str(row.get("name", "")).strip()
            ticker = row.get("ticker")
            aliases = [a for a in row.get("aliases", []) if isinstance(a, str)]

            if ticker:
                hit = re.search(rf"\b{re.escape(str(ticker))}\b", text)
                if hit and (name, ticker) not in seen:
                    seen.add((name, ticker))
                    results.append(
                        MatchedCompany(
                            company_name=name or str(ticker),
                            ticker=str(ticker),
                            confidence=0.95,
                            matched_text=hit.group(0),
                        )
                    )
                    continue

            for alias in aliases + ([name] if name else []):
                candidate = alias.strip()
                if len(candidate) < 3:
                    continue
                if (
                    candidate
                    and candidate.lower() in lowered
                    and (name, ticker) not in seen
                ):
                    seen.add((name, ticker))
                    results.append(
                        MatchedCompany(
                            company_name=name or candidate,
                            ticker=str(ticker) if ticker else None,
                            confidence=0.85,
                            matched_text=candidate,
                        )
                    )
                    break

        return results

    def _match_llm(
        self, text: str, candidates: list[MatchedCompany]
    ) -> list[MatchedCompany]:
        payload = [
            {
                "company_name": c.company_name,
                "ticker": c.ticker,
                "matched_text": c.matched_text,
                "confidence": c.confidence,
            }
            for c in candidates
        ]
        raw = self.llm_client.match_companies(text, payload)
        results: list[MatchedCompany] = []
        seen: set[tuple[str, str | None]] = set()

        for row in raw if isinstance(raw, list) else []:
            name = str(row.get("company_name", "")).strip()
            ticker = row.get("ticker")
            matched_text = str(row.get("matched_text", name or ticker or "")).strip()
            confidence = float(row.get("confidence", 0.8) or 0.8)
            if not name:
                continue
            key = (name, str(ticker) if ticker else None)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                MatchedCompany(
                    company_name=name,
                    ticker=str(ticker) if ticker else None,
                    confidence=confidence,
                    matched_text=matched_text,
                )
            )

        return results

    def _discover_companies_llm(self, text: str) -> list[MatchedCompany]:
        """Ask the LLM to extract company names when heuristics found nothing.

        Any discovered companies are persisted as new Firm rows.
        """
        logger.info("Running LLM company discovery on article text (%d chars)", len(text))
        raw = self.llm_client.discover_companies(text)
        logger.info("LLM discovery returned: %s", raw)
        results: list[MatchedCompany] = []
        seen: set[str] = set()

        for row in raw if isinstance(raw, list) else []:
            name = str(row.get("company_name", "")).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            ticker = row.get("ticker")
            ticker = str(ticker).strip() if ticker else None
            matched_text = str(row.get("matched_text", name)).strip()
            confidence = float(row.get("confidence", 0.7) or 0.7)

            firm = self.firm_repo.get_or_create_firm(name, ticker)

            aliases = row.get("aliases", [])
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        self.firm_repo.add_alias(
                            firm.id, alias.strip(), "llm_discovered", confidence=0.7
                        )

            results.append(
                MatchedCompany(
                    company_name=firm.full_name,
                    ticker=ticker,
                    confidence=confidence,
                    matched_text=matched_text,
                )
            )

        return results

    def get_or_create_firm(self, company_name: str, ticker: str | None = None) -> Firm:
        firm = self.firm_repo.get_or_create_firm(company_name, ticker)
        if ticker:
            self.firm_repo.add_alias(firm.id, ticker, "ticker", confidence=1.0)
        return firm

    def enrich_firm_profile(self, firm: Firm, article_text: str) -> None:
        if not self.llm_client or not getattr(self.llm_client, "has_api_key", False):
            return
        if not getattr(self.llm_client, "web_search_enabled", False):
            return

        current = {
            "id": firm.id,
            "full_name": firm.full_name,
            "nip": firm.nip,
            "regon": firm.regon,
            "krs": firm.krs,
            "country": firm.country,
            "market_ticker": firm.market_ticker,
            "market_exchange": firm.market_exchange,
        }
        enriched = self.llm_client.enrich_firm_profile(current, article_text)
        if not isinstance(enriched, dict):
            return

        aliases = enriched.pop("aliases", [])
        self.firm_repo.update_missing_fields(
            firm.id,
            nip=enriched.get("nip"),
            regon=enriched.get("regon"),
            krs=enriched.get("krs"),
            country=enriched.get("country"),
            market_ticker=enriched.get("market_ticker"),
            market_exchange=enriched.get("market_exchange"),
        )

        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    self.firm_repo.add_alias(
                        firm.id, alias.strip(), "enriched", confidence=0.75
                    )

    def add_alias(
        self, firm: Firm, alias: str, alias_type: str, confidence: float | None = None
    ) -> None:
        self.firm_repo.add_alias(firm.id, alias, alias_type, confidence=confidence)
