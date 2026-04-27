import json
import logging
from pathlib import Path

import click

from .database.seeder import get_keyword_id_map, seed_risk_keywords
from .database.session import SessionLocal
from .keywords.risk_keywords import RISK_KEYWORDS
from .pipeline.processor import ArticleProcessor
from .scanner.article_scorer import DEFAULT_THRESHOLD
from .scanner.regex_engine import RegexEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@click.group()
def cli() -> None:
    """RKR — Risk Keywords Regex | Step 1.5 between Scuttle Crab and Tarkov."""


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True), help="JSONL from Scuttle Crab")
@click.option("--output", "output_path", default="rkr_articles.jsonl", show_default=True, help="Passed articles for Tarkov")
@click.option("--rejected", "rejected_path", default="rkr_rejected.jsonl", show_default=True, help="Rejected articles")
@click.option("--threshold", default=DEFAULT_THRESHOLD, show_default=True, type=float, help="Minimum risk_score (0.0–1.0)")
@click.option("--seed-db/--no-seed-db", default=True, show_default=True, help="Seed risk_keywords table on startup")
def scan(
    input_path: str,
    output_path: str,
    rejected_path: str,
    threshold: float,
    seed_db: bool,
) -> None:
    """Scan articles and filter by risk keywords. Passes matched articles to Tarkov."""
    if seed_db:
        session = SessionLocal()
        try:
            n = seed_risk_keywords(session)
            click.echo(f"DB: seeded {n} new keywords into risk_keywords table")
        finally:
            session.close()

    processor = ArticleProcessor(threshold=threshold)
    stats = processor.process_file(
        Path(input_path), Path(output_path), Path(rejected_path)
    )
    click.echo(
        f"Done — total: {stats['total']} | "
        f"passed: {stats['passed']} | "
        f"rejected: {stats['rejected']} | "
        f"errors: {stats['errors']}"
    )
    click.echo(f"Output  → {output_path}")
    click.echo(f"Rejected → {rejected_path}")


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--threshold", default=DEFAULT_THRESHOLD, show_default=True, type=float)
def stats(input_path: str, threshold: float) -> None:
    """Dry-run: show statistics without writing any output files."""
    engine = RegexEngine()
    from .scanner.article_scorer import score_article

    total = passed = 0
    category_counts: dict[str, int] = {}

    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                raw = json.loads(line)
                title = raw.get("article", {}).get("title", "")
                text = raw.get("article", {}).get("text", "")
                matches = engine.scan(text, title)
                _, categories, passed_flag = score_article(matches, threshold)
                if passed_flag:
                    passed += 1
                    for cat in categories:
                        category_counts[cat] = category_counts.get(cat, 0) + 1
            except Exception:
                pass

    click.echo(f"Total    : {total}")
    click.echo(f"Passed   : {passed}")
    click.echo(f"Rejected : {total - passed}")
    if category_counts:
        click.echo("\nTop categories in passed articles:")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {cat:30s} {count}")


@cli.command("list-keywords")
@click.option("--category", default=None, help="Filter by category name")
def list_keywords(category: str | None) -> None:
    """List all hardcoded keywords, optionally filtered by category."""
    shown = 0
    for kw in RISK_KEYWORDS:
        if category and kw["category"] != category:
            continue
        click.echo(
            f"[{kw['category']:<22}] ({kw['lang']}) {kw['phrase']:<45}  weight={kw['weight']}"
        )
        shown += 1
    click.echo(f"\nTotal: {shown}")


@cli.command("keyword-ids")
def keyword_ids() -> None:
    """Show DB IDs for all seeded keywords (useful for Tarkov FK references)."""
    session = SessionLocal()
    try:
        id_map = get_keyword_id_map(session)
        for phrase, db_id in sorted(id_map.items()):
            click.echo(f"{db_id:>6}  {phrase}")
        click.echo(f"\nTotal in DB: {len(id_map)}")
    finally:
        session.close()


if __name__ == "__main__":
    cli()
