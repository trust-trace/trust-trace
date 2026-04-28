"""Company matcher tests."""

from __future__ import annotations

from tarkov.database.models import Firm, FirmAlias
from tarkov.extraction.company_matcher import CompanyMatcher
from tarkov.tests.conftest import create_test_session


def _seed_firm(db, name, ticker=None, aliases=None):
    """Insert a Firm + FirmAlias rows so the DB-backed matcher can find them."""
    firm = Firm(full_name=name, country="PL", market_ticker=ticker)
    db.add(firm)
    db.flush()
    db.add(FirmAlias(firm_id=firm.id, alias=name, alias_type="name", confidence=1.0, is_primary=True))
    if ticker:
        db.add(FirmAlias(firm_id=firm.id, alias=ticker, alias_type="ticker", confidence=1.0))
    for alias in aliases or []:
        if alias != name and alias != ticker:
            db.add(FirmAlias(firm_id=firm.id, alias=alias, alias_type="name", confidence=1.0))
    db.flush()
    return firm


def test_exact_ticker_match():
    db = create_test_session()
    _seed_firm(db, "Apple", ticker="AAPL", aliases=["Apple", "Apple Inc."])

    matcher = CompanyMatcher(db)
    matches = matcher.match_companies("AAPL announced earnings")

    assert len(matches) == 1
    assert matches[0].company_name == "Apple"


def test_company_name_alias_match():
    db = create_test_session()
    _seed_firm(db, "Apple", ticker="AAPL", aliases=["Apple Inc."])

    matcher = CompanyMatcher(db)
    matches = matcher.match_companies("Apple Inc. is under investigation")

    assert len(matches) == 1
    assert matches[0].ticker == "AAPL"


def test_get_or_create_firm():
    db = create_test_session()
    matcher = CompanyMatcher(db)
    firm_1 = matcher.get_or_create_firm("Acme Corp", "ACME")
    firm_2 = matcher.get_or_create_firm("Acme Corp", "ACME")

    assert firm_1.id == firm_2.id
    assert firm_1.market_ticker == "ACME"


def test_enrich_firm_profile_fills_missing_fields_and_aliases():
    db = create_test_session()
    _seed_firm(db, "Acme Corp", ticker="ACME", aliases=["Acme Corp"])

    class FakeLLMClient:
        has_api_key = True
        web_search_enabled = True

        def enrich_firm_profile(self, firm: dict, article_text: str):
            return {
                "nip": "1234567890",
                "country": "PL",
                "market_exchange": "NASDAQ",
                "aliases": ["Acme Holdings"],
            }

    matcher = CompanyMatcher(db, llm_client=FakeLLMClient())
    firm = matcher.get_or_create_firm("Acme Corp", "ACME")

    matcher.enrich_firm_profile(firm, "Acme Corp is based in Poland")

    refreshed = db.get(type(firm), firm.id)
    assert refreshed is not None
    assert refreshed.nip == "1234567890"
    assert refreshed.country == "PL"
    assert refreshed.market_ticker == "ACME"
    assert refreshed.market_exchange == "NASDAQ"
    assert any(alias.alias == "Acme Holdings" for alias in refreshed.aliases)


def test_enrich_firm_profile_does_not_overwrite_existing_market_fields():
    db = create_test_session()
    _seed_firm(db, "Acme Corp", ticker="ACME", aliases=["Acme Corp"])

    class FakeLLMClient:
        has_api_key = True
        web_search_enabled = True

        def enrich_firm_profile(self, firm: dict, article_text: str):
            return {
                "market_ticker": "",
                "market_exchange": "",
            }

    matcher = CompanyMatcher(db, llm_client=FakeLLMClient())
    firm = matcher.get_or_create_firm("Acme Corp", "ACME")
    firm.market_exchange = "NASDAQ"
    db.flush()

    matcher.enrich_firm_profile(firm, "Acme Corp keeps its listing")

    refreshed = db.get(type(firm), firm.id)
    assert refreshed is not None
    assert refreshed.market_ticker == "ACME"
    assert refreshed.market_exchange == "NASDAQ"


def test_discover_companies_creates_new_firms():
    db = create_test_session()

    class FakeLLMClient:
        has_api_key = True

        def discover_companies(self, article_text: str):
            return [
                {
                    "company_name": "Zondacrypto sp. z o.o.",
                    "ticker": None,
                    "matched_text": "Zondacrypto",
                    "confidence": 0.85,
                    "aliases": ["Zonda Crypto", "Zondacrypto"],
                }
            ]

    matcher = CompanyMatcher(db, llm_client=FakeLLMClient())
    matches = matcher.match_companies("Zondacrypto faces investigation for fraud")

    assert len(matches) == 1
    assert matches[0].company_name == "Zondacrypto sp. z o.o."

    firm = db.query(Firm).filter_by(full_name="Zondacrypto sp. z o.o.").one()
    alias_names = [a.alias for a in firm.aliases]
    assert "Zonda Crypto" in alias_names
    assert "Zondacrypto" in alias_names
