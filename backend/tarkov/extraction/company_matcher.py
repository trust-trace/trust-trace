"""Company matching and firm upsert logic."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tarkov.database.models import Firm
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.llm.client import LLMClient
from tarkov.utils.text_utils import normalize_whitespace


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
        company_reference_path: str,
        llm_client: LLMClient | None = None,
    ):
        self.firm_repo = FirmRepository(db_session)
        self.company_reference = self._load_company_reference(company_reference_path)
        self.llm_client = llm_client

    @staticmethod
    def _load_company_reference(path_value: str) -> list[dict]:
        path = Path(path_value)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload if isinstance(payload, list) else []

    def match_companies(self, article_text: str) -> list[MatchedCompany]:
        text = normalize_whitespace(article_text)
        lowered = text.lower()
        heuristic_matches = self._match_heuristic(text, lowered)

        if self.llm_client and self.llm_client.has_api_key and heuristic_matches:
            llm_matches = self._match_llm(text, heuristic_matches)
            if llm_matches:
                return llm_matches

        return heuristic_matches

    def _match_heuristic(self, text: str, lowered: str) -> list[MatchedCompany]:
        results: list[MatchedCompany] = []
        seen: set[tuple[str, str | None]] = set()

        for row in self.company_reference:
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
