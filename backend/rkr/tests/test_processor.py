import json
from pathlib import Path

import pytest

from ..pipeline.processor import ArticleProcessor

FIXTURES = Path(__file__).parent / "fixtures" / "sample_articles.jsonl"


@pytest.fixture
def processor() -> ArticleProcessor:
    return ArticleProcessor(threshold=0.3)


def _load_fixture(path: Path = FIXTURES) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_process_article_returns_enriched(processor: ArticleProcessor) -> None:
    articles = _load_fixture()
    raw = articles[0]  # money laundering article — should pass
    result = processor.process_article(raw)
    assert result.rkr.risk_score > 0.0
    assert result.rkr.passed_threshold is True
    assert len(result.rkr.matched_keywords) > 0


def test_neutral_article_does_not_pass(processor: ArticleProcessor) -> None:
    articles = _load_fixture()
    raw = articles[2]  # Series B funding — no risk keywords
    result = processor.process_article(raw)
    assert result.rkr.passed_threshold is False


def test_polish_article_detected(processor: ArticleProcessor) -> None:
    articles = _load_fixture()
    raw = articles[1]  # Polish spółka fasadowa article
    result = processor.process_article(raw)
    assert result.rkr.passed_threshold is True
    categories = result.rkr.categories_hit
    assert any(c in categories for c in ("tax_evasion", "money_laundering", "regulatory_action"))


def test_process_file_writes_correct_files(
    processor: ArticleProcessor, tmp_path: Path
) -> None:
    out = tmp_path / "passed.jsonl"
    rej = tmp_path / "rejected.jsonl"

    stats = processor.process_file(FIXTURES, out, rej)

    assert stats["total"] == 4
    assert stats["errors"] == 0
    assert stats["passed"] + stats["rejected"] == stats["total"]

    passed_articles = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    for article in passed_articles:
        assert article["rkr"]["passed_threshold"] is True


def test_enriched_article_has_rkr_field(processor: ArticleProcessor) -> None:
    articles = _load_fixture()
    result = processor.process_article(articles[0])
    dumped = result.model_dump()
    assert "rkr" in dumped
    assert "risk_score" in dumped["rkr"]
    assert "matched_keywords" in dumped["rkr"]
    assert "categories_hit" in dumped["rkr"]
    assert "passed_threshold" in dumped["rkr"]
