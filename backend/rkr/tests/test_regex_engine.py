import pytest

from ..scanner.regex_engine import RegexEngine


@pytest.fixture(scope="module")
def engine() -> RegexEngine:
    return RegexEngine()


def test_detects_money_laundering_in_text(engine: RegexEngine) -> None:
    matches = engine.scan("The firm was charged with money laundering.", "")
    keywords = [m.keyword for m in matches]
    assert "money laundering" in keywords


def test_detects_keyword_in_title(engine: RegexEngine) -> None:
    matches = engine.scan("Some body text.", "Bank accused of money laundering")
    title_hits = [m for m in matches if m.in_title]
    assert any(m.keyword == "money laundering" for m in title_hits)


def test_detects_polish_keyword(engine: RegexEngine) -> None:
    matches = engine.scan("Spółka została oskarżona o pranie pieniędzy.", "")
    keywords = [m.keyword for m in matches]
    assert "pranie pieniędzy" in keywords


def test_case_insensitive(engine: RegexEngine) -> None:
    matches = engine.scan("Authorities confirmed MONEY LAUNDERING activities.", "")
    keywords = [m.keyword for m in matches]
    assert "money laundering" in keywords


def test_no_match_returns_empty(engine: RegexEngine) -> None:
    matches = engine.scan("The company posted strong quarterly earnings.", "")
    assert matches == []


def test_occurrences_counted(engine: RegexEngine) -> None:
    text = "fraud was confirmed. More fraud evidence appeared. Investigators called it clear fraud."
    matches = engine.scan(text, "")
    fraud_match = next((m for m in matches if m.keyword == "fraud"), None)
    assert fraud_match is not None
    assert fraud_match.occurrences == 3


def test_context_extracted(engine: RegexEngine) -> None:
    matches = engine.scan("The court ruled this was insider trading by the fund manager.", "")
    match = next((m for m in matches if m.keyword == "insider trading"), None)
    assert match is not None
    assert "insider trading" in match.context


def test_sanctions_ofac(engine: RegexEngine) -> None:
    matches = engine.scan("The entity was added to the OFAC blacklist.", "")
    keywords = [m.keyword for m in matches]
    assert "OFAC" in keywords or "blacklist" in keywords


def test_multiple_categories_detected(engine: RegexEngine) -> None:
    text = "The firm faced SEC investigation for money laundering and insider trading."
    matches = engine.scan(text, "")
    categories = {m.category for m in matches}
    assert "regulatory_action" in categories
    assert "money_laundering" in categories
    assert "fraud" in categories
