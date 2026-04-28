from __future__ import annotations

import json
import logging
import sys

import click
from sqlalchemy import select, text

import eem.config as config
from eem import FirmNotFoundError, enrich_firm
from eem.database._repos import _EventReader
from eem.database.models import FirmScore
from eem.database.session import get_db, init_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--firm-id", type=int, default=None, help="Firm PK from firm table")
@click.option("--firm-name", default=None, help="Partial firm name (ILIKE match)")
def enrich(firm_id: int | None, firm_name: str | None) -> None:
    """Enrich classical events for a firm and compute its AML score."""
    if firm_id is None and firm_name is None:
        click.echo("Provide --firm-id or --firm-name", err=True)
        sys.exit(1)

    if firm_id is None:
        firm_id = _resolve_firm_id(firm_name)

    try:
        score = enrich_firm(firm_id)
        click.echo(f"firm_id={firm_id}  score={score:.1f}")
    except FirmNotFoundError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@cli.command("enrich-all")
def enrich_all() -> None:
    """Enrich all firms that have unprocessed classical events."""
    _init_db()
    with get_db() as db:
        firm_ids = _EventReader(db).get_unprocessed_firm_ids()

    if not firm_ids:
        click.echo("No firms with unprocessed events.")
        return

    for fid in firm_ids:
        try:
            score = enrich_firm(fid)
            click.echo(f"firm_id={fid}  score={score:.1f}")
        except FirmNotFoundError as exc:
            click.echo(f"firm_id={fid}  SKIPPED: {exc}", err=True)
        except Exception as exc:
            click.echo(f"firm_id={fid}  FAILED: {exc}", err=True)


@cli.command()
@click.option("--firm-id", type=int, required=True)
def status(firm_id: int) -> None:
    """Print current score for a firm — no LLM calls."""
    _init_db()
    with get_db() as db:
        row = db.execute(
            select(FirmScore).where(FirmScore.firm_id == firm_id)
        ).scalar_one_or_none()

    if row is None:
        click.echo(f"firm_id={firm_id}: no score yet")
        return

    history = json.loads(row.score_history)
    keywords = json.loads(row.keywords)
    click.echo(f"score={row.score}  risk={row.risk}  trend={row.trend:+d}")
    click.echo(f"history={history}")
    click.echo(f"keywords={keywords}")
    click.echo(f"computed_at={row.computed_at}")


def _resolve_firm_id(name: str) -> int:
    _init_db()
    with get_db() as db:
        rows = db.execute(
            text("SELECT id, full_name FROM firm WHERE full_name ILIKE :name"),
            {"name": f"%{name}%"},
        ).fetchall()

    if not rows:
        click.echo(f"No firm matching '{name}'", err=True)
        sys.exit(1)
    if len(rows) > 1:
        matches = ", ".join(f"{r.id}:{r.full_name}" for r in rows)
        click.echo(f"Multiple matches — use --firm-id. Found: {matches}", err=True)
        sys.exit(1)
    return rows[0].id


def _init_db() -> None:
    if not config.DATABASE_URL:
        click.echo("DATABASE_URL is not set", err=True)
        sys.exit(1)
    init_engine(config.DATABASE_URL)


if __name__ == "__main__":
    cli()
