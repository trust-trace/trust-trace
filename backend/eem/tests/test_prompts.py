from datetime import datetime

from eem._types import _EventRow, _PersonRow, _SourceRow
from eem.llm._prompts import SYSTEM_PROMPT, build_user_message


def _event(**overrides) -> _EventRow:
    defaults = dict(
        event_id="test-uuid-1",
        firm_id=1,
        event_type="fraud",
        title="Test event title",
        risk_level=7,
        occurred_at=datetime(2024, 3, 15),
        source_text_quote=None,
        sources=[],
        people=[],
    )
    return _EventRow(**{**defaults, **overrides})


def test_firm_name_present():
    msg = build_user_message(_event(), "PKN Orlen")
    assert "PKN Orlen" in msg


def test_event_type_present():
    msg = build_user_message(_event(event_type="money_laundering"), "Corp")
    assert "money_laundering" in msg


def test_risk_level_present():
    msg = build_user_message(_event(risk_level=9), "Corp")
    assert "9/10" in msg


def test_date_formatted():
    msg = build_user_message(_event(occurred_at=datetime(2024, 3, 15)), "Corp")
    assert "2024-03-15" in msg


def test_source_quote_included():
    msg = build_user_message(_event(source_text_quote="Spółka prała pieniądze."), "Corp")
    assert "Spółka prała pieniądze." in msg


def test_no_source_quote_section_absent():
    msg = build_user_message(_event(source_text_quote=None), "Corp")
    assert "Source quote" not in msg


def test_sources_section_included():
    source = _SourceRow(
        title="Gazeta Wyborcza",
        url="https://gazeta.pl/a",
        published_at=datetime(2024, 3, 15),
        content_excerpt="Artykuł o przestępstwie.",
    )
    msg = build_user_message(_event(sources=[source]), "Corp")
    assert "Sources:" in msg
    assert "Gazeta Wyborcza" in msg
    assert "Artykuł o przestępstwie." in msg


def test_no_sources_section_absent():
    msg = build_user_message(_event(sources=[]), "Corp")
    assert "Sources:" not in msg


def test_people_section_included():
    person = _PersonRow(name="Jan Kowalski", role="CFO", role_in_event="suspect")
    msg = build_user_message(_event(people=[person]), "Corp")
    assert "People involved:" in msg
    assert "Jan Kowalski" in msg
    assert "CFO" in msg
    assert "suspect" in msg


def test_no_people_section_absent():
    msg = build_user_message(_event(people=[]), "Corp")
    assert "People involved:" not in msg


def test_person_missing_role_uses_fallback():
    person = _PersonRow(name="Anna Nowak", role=None, role_in_event=None)
    msg = build_user_message(_event(people=[person]), "Corp")
    assert "unknown role" in msg
    assert "involved" in msg


def test_source_missing_published_at():
    source = _SourceRow(
        title="Bankier.pl",
        url="https://bankier.pl/a",
        published_at=None,
        content_excerpt="Treść.",
    )
    msg = build_user_message(_event(sources=[source]), "Corp")
    assert "unknown date" in msg


def test_message_ends_with_instruction():
    msg = build_user_message(_event(), "Corp")
    assert msg.strip().endswith("Return your JSON analysis now.")


def test_system_prompt_has_required_fields():
    for field in ("sentiment", "impact", "source_tier", "keywords", "excerpt", "entities"):
        assert field in SYSTEM_PROMPT


def test_system_prompt_defines_tiers():
    assert "tier-1" in SYSTEM_PROMPT
    assert "tier-2" in SYSTEM_PROMPT
    assert "tier-3" in SYSTEM_PROMPT
