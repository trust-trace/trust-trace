from .regex_engine import EngineMatch
from reasoning.collectors.rkr_collector import RKRTraceCollector
from reasoning.schemas import RKRReasoningTrace

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
    article_id: str | None = None,
) -> tuple[float, list[str], bool, RKRReasoningTrace]:
    collector = RKRTraceCollector(article_id)
    
    # Record keyword matches
    for match in matches:
        context_snippet = getattr(match, "context_snippet", "")[:100] or ""
        collector.record_keyword_match(
            keyword=match.keyword,
            category=match.category,
            weight=match.weight,
            in_title=match.in_title,
            context_snippet=context_snippet,
            occurrences=getattr(match, "occurrences", 1),
            title_multiplier=_TITLE_MULTIPLIER,
        )
    
    # Calculate risk score
    risk_score = compute_risk_score(matches)
    
    # Record score calculation
    raw_sum = sum(
        m.weight * (_TITLE_MULTIPLIER if m.in_title else 1.0)
        for m in matches
    ) if matches else 0.0
    collector.record_score_calculation(
        raw_sum=raw_sum,
        normalization_divisor=_NORMALIZATION,
        final_risk_score=risk_score,
        capped_at_1_0=(raw_sum / _NORMALIZATION > 1.0) if matches else False,
    )
    
    # Check threshold
    categories_hit = list({m.category for m in matches})
    passed = risk_score >= threshold
    collector.record_threshold_decision(threshold, passed)
    
    trace = collector.collect()
    return risk_score, categories_hit, passed, trace
