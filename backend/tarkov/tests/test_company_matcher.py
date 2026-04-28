"""Company matcher tests."""

from __future__ import annotations

import json

from tarkov.extraction.company_matcher import CompanyMatcher
from tarkov.tests.conftest import create_test_session


def test_exact_ticker_match(tmp_path):
    reference = [
        {"name": "Apple", "ticker": "AAPL", "aliases": ["Apple", "Apple Inc."]},
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(reference), encoding="utf-8")

    db = create_test_session()
    matcher = CompanyMatcher(db, str(path))
    matches = matcher.match_companies("AAPL announced earnings")

    assert len(matches) == 1
    assert matches[0].company_name == "Apple"


def test_company_name_alias_match(tmp_path):
    reference = [{"name": "Apple", "ticker": "AAPL", "aliases": ["Apple Inc."]}]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(reference), encoding="utf-8")

    db = create_test_session()
    matcher = CompanyMatcher(db, str(path))
    matches = matcher.match_companies("Apple Inc. is under investigation")

    assert len(matches) == 1
    assert matches[0].ticker == "AAPL"


def test_get_or_create_firm(tmp_path):
    path = tmp_path / "companies.json"
    path.write_text("[]", encoding="utf-8")

    db = create_test_session()
    matcher = CompanyMatcher(db, str(path))
    firm_1 = matcher.get_or_create_firm("Acme Corp", "ACME")
    firm_2 = matcher.get_or_create_firm("Acme Corp", "ACME")

    assert firm_1.id == firm_2.id


def test_enrich_firm_profile_fills_missing_fields_and_aliases(tmp_path):
    reference = [{"name": "Acme Corp", "ticker": "ACME", "aliases": ["Acme Corp"]}]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(reference), encoding="utf-8")

    class FakeLLMClient:
        has_api_key = True
        web_search_enabled = True

        def enrich_firm_profile(self, firm: dict, article_text: str):
            return {
                "nip": "1234567890",
                "country": "PL",
                "aliases": ["Acme Holdings"],
            }

    db = create_test_session()
    matcher = CompanyMatcher(db, str(path), llm_client=FakeLLMClient())
    firm = matcher.get_or_create_firm("Acme Corp", "ACME")

    matcher.enrich_firm_profile(firm, "Acme Corp is based in Poland")

    refreshed = db.get(type(firm), firm.id)
    assert refreshed is not None
    assert refreshed.nip == "1234567890"
    assert refreshed.country == "PL"
    assert any(alias.alias == "Acme Holdings" for alias in refreshed.aliases)
