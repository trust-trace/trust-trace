"""CLI entrypoint for Tarkov."""

from __future__ import annotations

import json

import click

from tarkov.config import Config
from tarkov.database.session import SessionLocal, init_engine
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.schemas.article import ArticleIn
from tarkov.storage.article_reader import ArticleReader
from tarkov.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


@click.group()
def cli() -> None:
    """Tarkov command line interface."""


@cli.command("process-articles")
@click.option("--input-source", default="jsonl", show_default=True)
@click.option("--input-path", default="articles.jsonl", show_default=True)
@click.option("--batch-size", default=100, show_default=True, type=int)
def process_articles(input_source: str, input_path: str, batch_size: int) -> None:
    """Process articles from source and extract events."""
    config = Config.from_env()
    setup_logging(config.log_level)
    init_engine(config.database_url)
    db_session = SessionLocal()

    reader = ArticleReader(input_source, input_path)
    processor = ArticleProcessor(db_session, config)

    for batch in reader.read_article_batch(batch_size):
        processor.process_articles_batch(batch)

    logger.info("All articles processed")


@cli.command("process-single")
@click.argument("article_path")
def process_single(article_path: str) -> None:
    """Process a single article from JSON file."""
    config = Config.from_env()
    setup_logging(config.log_level)
    init_engine(config.database_url)
    db_session = SessionLocal()

    with open(article_path, "r", encoding="utf-8") as handle:
        article_data = json.load(handle)

    article = ArticleIn.model_validate(article_data)
    processor = ArticleProcessor(db_session, config)
    result = processor.process_article(article)
    if result is None:
        logger.warning("Article processed without company matches")
    else:
        logger.info("Processed article_id=%s", result.article_id)


@cli.command("serve")
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve(host: str | None, port: int | None) -> None:
    """Run HTTP API for Scuttle Crab -> Tarkov ingestion."""
    config = Config.from_env()
    setup_logging(config.log_level)

    import uvicorn

    from tarkov.api import create_app

    app = create_app(config)
    uvicorn.run(
        app,
        host=host or config.api_host,
        port=port or config.api_port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    cli()
