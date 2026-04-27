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
