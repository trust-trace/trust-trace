"""CLI entrypoints for Tarkov processing and API service."""

from __future__ import annotations

import json

import click

from tarkov.config import Config
from tarkov.database.session import SessionLocal, init_engine, init_neo4j
from tarkov.pipeline.processor import ArticleProcessor
from tarkov.pipeline.stage3_dispatch import build_stage3_result_emitter
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
    config = Config.from_env()
    setup_logging(config.log_level)
    init_engine(config.database_url)
    init_neo4j(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    session = SessionLocal()

    try:
        processor = ArticleProcessor(session, config, result_emitter=build_stage3_result_emitter(config))
        for batch in ArticleReader(input_source, input_path).read_article_batch(batch_size):
            processor.process_articles_batch(batch)
        logger.info("All articles processed")
    finally:
        session.close()


@cli.command("process-single")
@click.argument("article_path")
def process_single(article_path: str) -> None:
    config = Config.from_env()
    setup_logging(config.log_level)
    init_engine(config.database_url)
    init_neo4j(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    session = SessionLocal()

    try:
        with open(article_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        article = ArticleIn.model_validate(payload)
        result = ArticleProcessor(session, config, result_emitter=build_stage3_result_emitter(config)).process_article(
            article
        )
        if result is None:
            logger.warning("Article processed without company matches")
        else:
            logger.info("Processed article_id=%s", result.article_id)
    finally:
        session.close()


@cli.command("serve")
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve(host: str | None, port: int | None) -> None:
    config = Config.from_env()
    setup_logging(config.log_level)
    init_neo4j(config.neo4j_uri, config.neo4j_user, config.neo4j_password)

    import uvicorn

    from tarkov.api import create_app

    uvicorn.run(
        create_app(config),
        host=host or config.api_host,
        port=port or config.api_port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    cli()
