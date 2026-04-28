from __future__ import annotations

import click
import uvicorn

from nsa.api import create_app
from nsa.config import NSAConfig


@click.group()
def cli() -> None:
    """NSA service commands."""


@cli.command("serve")
def serve() -> None:
    config = NSAConfig.from_env()
    uvicorn.run(
        create_app(database_url=config.database_url),
        host=config.api_host,
        port=config.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
