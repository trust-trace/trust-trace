import pytest

from ..scanner.article_scorer import DEFAULT_THRESHOLD, compute_risk_score, score_article
from ..scanner.regex_engine import EngineMatch


def _match(keyword: str, category: str, weight: float, in_title: bool = False) -> EngineMatch:
    return EngineMatch(
        keyword=keyword,
        category=category,
        weight=weight,
        in_title=in_title,
        context="...",
        occurrences=1,
    )


def test_empty_matches_returns_zero() -> None:
    assert compute_risk_score([]) == 0.0


def test_single_high_weight_match() -> None:
    matches = [_match("money laundering", "money_laundering", 0.9)]
    score = compute_risk_score(matches)
    assert score > 0.0
    assert score <= 1.0


def test_title_hit_scores_higher() -> None:
    body_match = _match("fraud", "fraud", 0.85, in_title=False)
    title_match = _match("fraud", "fraud", 0.85, in_title=True)
    assert compute_risk_score([title_match]) > compute_risk_score([body_match])


def test_score_capped_at_one() -> None:
    many_matches = [
        _match(f"kw{i}", "sanctions", 0.95, in_title=True) for i in range(20)
    ]
    assert compute_risk_score(many_matches) == 1.0


def test_passed_threshold_true() -> None:
    matches = [_match("money laundering", "money_laundering", 0.9)]
    score, categories, passed = score_article(matches, threshold=0.1)
    assert passed is True
    assert "money_laundering" in categories


def test_passed_threshold_false_for_low_score() -> None:
    matches = [_match("bankruptcy", "bankruptcy", 0.6)]
    score, _, passed = score_article(matches, threshold=0.9)
    assert passed is False


def test_categories_hit_deduped() -> None:
    matches = [
        _match("fraud", "fraud", 0.85),
        _match("embezzlement", "fraud", 0.85),
        _match("money laundering", "money_laundering", 0.9),
    ]
    _, categories, _ = score_article(matches)
    assert len(categories) == 2
    assert set(categories) == {"fraud", "money_laundering"}
