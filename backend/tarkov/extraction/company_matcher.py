"""Company matching and firm creation logic."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tarkov.database.models import Firm
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.utils.text_utils import normalize_whitespace


@dataclass
class MatchedCompany:
    company_name: str
    ticker: str | None
    confidence: float
    matched_text: str


class CompanyMatcher:
    def __init__(self, db_session: Session, company_reference_path: str):
        self.firm_repo = FirmRepository(db_session)
        self.company_reference = self._load_company_reference(company_reference_path)

    def _load_company_reference(self, company_reference_path: str) -> list[dict]:
        path = Path(company_reference_path)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        return []

    def match_companies(self, article_text: str) -> list[MatchedCompany]:
        text = normalize_whitespace(article_text)
        lowered = text.lower()
        results: list[MatchedCompany] = []
        seen: set[tuple[str, str | None]] = set()

        for company in self.company_reference:
            name = company.get("name", "").strip()
            ticker = company.get("ticker")
            aliases = [a for a in company.get("aliases", []) if isinstance(a, str)]

            if ticker:
                pattern = rf"\b{re.escape(ticker)}\b"
                match = re.search(pattern, text)
                if match and (name, ticker) not in seen:
                    results.append(MatchedCompany(name, ticker, 0.95, match.group(0)))
                    seen.add((name, ticker))
                    continue

            for alias in aliases + ([name] if name else []):
                alias_clean = alias.strip()
                if not alias_clean:
                    continue
                if alias_clean.lower() in lowered and (name, ticker) not in seen:
                    results.append(MatchedCompany(name or alias_clean, ticker, 0.85, alias_clean))
                    seen.add((name, ticker))
                    break

        return results

    def get_or_create_firm(self, company_name: str, ticker: str | None = None) -> Firm:
        firm = self.firm_repo.get_or_create_firm(company_name, ticker)
        if ticker:
            self.firm_repo.add_alias(firm.id, ticker, "ticker")
        return firm

    def add_alias(self, firm: Firm, alias: str, alias_type: str, confidence: float | None = None) -> None:
        self.firm_repo.add_alias(
            firm_id=firm.id,
            alias=alias,
            alias_type=alias_type,
            confidence=confidence,
        )
