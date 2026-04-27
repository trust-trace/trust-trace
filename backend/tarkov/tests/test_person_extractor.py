"""Person extractor tests."""

from __future__ import annotations

from tarkov.extraction.person_extractor import PersonExtractor
from tarkov.tests.fixtures.sample_articles import SAMPLE_ARTICLE_1


def test_role_keyword_detection():
    extractor = PersonExtractor()
    people = extractor.extract_people_keyword_based(SAMPLE_ARTICLE_1, ["fraud investigation"])
    assert any(person.role in {"ceo", "director", "owner"} for person in people)


def test_name_pattern_matching():
    extractor = PersonExtractor()
    names = extractor.match_name_patterns("CEO John Smith and Dr. Jane Doe were questioned.")
    assert "John Smith" in names or "Jane Doe" in names


def test_company_like_fragments_are_filtered():
    extractor = PersonExtractor()
    names = extractor.match_name_patterns("Acme Corp and Director Jane Doe were mentioned.")
    assert "Acme Corp" not in names
    assert "Director Jane" not in names
    assert "Jane Doe" in names
