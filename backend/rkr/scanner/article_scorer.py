from .regex_engine import EngineMatch

DEFAULT_THRESHOLD: float = 0.3
_TITLE_MULTIPLIER: float = 1.5
_NORMALIZATION: float = 3.0


def compute_risk_score(matches: list[EngineMatch]) -> float:
    if not matches:
        return 0.0
    raw = sum(
        m.weight * (_TITLE_MULTIPLIER if m.in_title else 1.0)
        for m in matches
    )
    return min(raw / _NORMALIZATION, 1.0)


def score_article(
    matches: list[EngineMatch],
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[float, list[str], bool]:
    risk_score = compute_risk_score(matches)
    categories_hit = list({m.category for m in matches})
    passed = risk_score >= threshold
    return risk_score, categories_hit, passed
