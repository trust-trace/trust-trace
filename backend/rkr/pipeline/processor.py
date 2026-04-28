import json
import logging
from pathlib import Path

from ..scanner.article_scorer import DEFAULT_THRESHOLD, score_article
from ..scanner.language_engine import LanguageEngineCache
from ..scanner.regex_engine import EngineMatch
from ..schemas.rkr_result import EnrichedArticle, RkrMatch, RkrResult
from reasoning.storage import ReasoningTraceRepository

logger = logging.getLogger(__name__)


def _build_rkr_result(
    matches: list[EngineMatch],
    threshold: float,
    article_id: str | None = None,
) -> tuple[RkrResult, dict]:
    risk_score, categories_hit, passed, trace = score_article(matches, threshold, article_id)
    return (
        RkrResult(
            matched_keywords=[
                RkrMatch(
                    keyword=m.keyword,
                    category=m.category,
                    weight=m.weight,
                    in_title=m.in_title,
                    context=m.context,
                    occurrences=m.occurrences,
                )
                for m in matches
            ],
            categories_hit=categories_hit,
            risk_score=risk_score,
            passed_threshold=passed,
        ),
        trace.model_dump(),
    )


class ArticleProcessor:
    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        self._engine_cache = LanguageEngineCache()

    def process_article(self, raw: dict, db_session=None) -> EnrichedArticle:
        lang = raw.get("article", {}).get("language", "en")
        title = raw.get("article", {}).get("title", "")
        text = raw.get("article", {}).get("text", "")
        article_id = raw.get("metadata", {}).get("id", None) or raw.get("article", {}).get("id", None)

        engine = self._engine_cache.get_engine(lang)
        matches = engine.scan(text, title)
        rkr_result, trace_data = _build_rkr_result(matches, self.threshold, article_id)
        
        # Store trace if database session is provided
        if db_session and article_id:
            trace_repo = ReasoningTraceRepository(db_session)
            trace_repo.save(
                classifier_name="RKR",
                entity_type="article",
                entity_id=str(article_id),
                trace_data=trace_data,
                correlation_id=None,
            )

        return EnrichedArticle(
            source=raw.get("source", {}),
            article=raw.get("article", {}),
            metadata=raw.get("metadata", {}),
            rkr=rkr_result,
        )

    def process_file(
        self,
        input_path: Path,
        output_path: Path,
        rejected_path: Path,
    ) -> dict[str, int]:
        stats: dict[str, int] = {
            "total": 0,
            "passed": 0,
            "rejected": 0,
            "errors": 0,
        }

        with (
            open(input_path, encoding="utf-8") as inp,
            open(output_path, "w", encoding="utf-8") as out,
            open(rejected_path, "w", encoding="utf-8") as rej,
        ):
            for line in inp:
                line = line.strip()
                if not line:
                    continue
                stats["total"] += 1
                try:
                    raw = json.loads(line)
                    enriched = self.process_article(raw)
                    serialized = json.dumps(
                        enriched.model_dump(), ensure_ascii=False
                    )
                    if enriched.rkr.passed_threshold:
                        out.write(serialized + "\n")
                        stats["passed"] += 1
                    else:
                        rej.write(serialized + "\n")
                        stats["rejected"] += 1
                except Exception as exc:
                    logger.error("Failed to process article: %s", exc)
                    stats["errors"] += 1

        return stats
