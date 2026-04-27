"""Company matching and firm upsert logic."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tarkov.database.models import Firm
from tarkov.database.repositories.firm_repo import FirmRepository
from tarkov.utils.text_utils import normalize_whitespace


@dataclass(slots=True)
class MatchedCompany:
    company_name: str
    ticker: str | None
    confidence: float
    matched_text: str


class CompanyMatcher:
    def __init__(self, db_session: Session, company_reference_path: str):
        self.firm_repo = FirmRepository(db_session)
        self.company_reference = self._load_company_reference(company_reference_path)

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
                if candidate and candidate.lower() in lowered and (name, ticker) not in seen:
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

    def get_or_create_firm(self, company_name: str, ticker: str | None = None) -> Firm:
        firm = self.firm_repo.get_or_create_firm(company_name, ticker)
        if ticker:
            self.firm_repo.add_alias(firm.id, ticker, "ticker", confidence=1.0)
        return firm

    def add_alias(self, firm: Firm, alias: str, alias_type: str, confidence: float | None = None) -> None:
        self.firm_repo.add_alias(firm.id, alias, alias_type, confidence=confidence)
