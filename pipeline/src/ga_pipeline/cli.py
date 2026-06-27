"""Typer CLI entry point for the graduation-arena data pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import typer

from ga_pipeline.oai import DEFAULT_SET_SPEC, HarvestConfig, OAIClient
from ga_pipeline.store import ProcessingStore

logger = logging.getLogger("ga_pipeline")
PIPELINE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STORE = PIPELINE_DIR.parent / "local" / "processing.sqlite"

app = typer.Typer(
    name="ga-pipeline",
    help="Scrape, parse, aggregate, and build static JSON for graduation-arena.",
    no_args_is_help=True,
    add_completion=False,
)


def _todo(stage: str) -> None:
    """Report that a pipeline stage is not implemented yet."""
    logger.info("%s: not implemented yet (TODO)", stage)
    typer.echo(f"{stage}: not implemented yet (TODO)")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Set up logging shared by every subcommand."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def scrape(
    store: Annotated[
        Path,
        typer.Option(
            "--store",
            help="SQLite processing store to write raw thesis records into.",
        ),
    ] = DEFAULT_STORE,
    from_date: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Inclusive OAI-PMH datestamp lower bound (YYYY-MM-DD).",
        ),
    ] = None,
    until_date: Annotated[
        str | None,
        typer.Option(
            "--until",
            help="Inclusive OAI-PMH datestamp upper bound (YYYY-MM-DD).",
        ),
    ] = None,
    set_spec: Annotated[
        str,
        typer.Option(
            "--set",
            help="OAI-PMH setSpec to harvest.",
        ),
    ] = DEFAULT_SET_SPEC,
    endpoint: Annotated[
        str,
        typer.Option(
            "--endpoint",
            help="OAI-PMH endpoint.",
        ),
    ] = "https://dspace.cuni.cz/oai/request",
    delay_seconds: Annotated[
        float,
        typer.Option(
            "--delay-seconds",
            min=0.0,
            help="Delay between paged OAI requests.",
        ),
    ] = 2.0,
    contact_email: Annotated[
        str | None,
        typer.Option(
            "--contact-email",
            envvar="GA_PIPELINE_CONTACT_EMAIL",
            help="Contact email included in the User-Agent.",
        ),
    ] = None,
) -> None:
    """Harvest OAI-PMH thesis metadata into the local processing store."""
    email = contact_email or os.getenv("GA_PIPELINE_CONTACT_EMAIL")
    user_agent = (
        f"graduation-arena/0.0.0 (metadata research harvester; contact: {email})"
        if email
        else HarvestConfig().user_agent
    )
    config = HarvestConfig(
        endpoint=endpoint,
        set_spec=set_spec,
        from_date=from_date,
        until_date=until_date,
        user_agent=user_agent,
        delay_seconds=delay_seconds,
    )

    count = 0
    with ProcessingStore(store) as processing_store:
        for thesis in OAIClient(config).list_records():
            processing_store.upsert_raw_thesis(thesis)
            count += 1

    typer.echo(f"scrape: stored {count} raw thesis record(s) in {store}")


@app.command()
def parse() -> None:
    """Normalise scraped theses into structured records (TODO)."""
    _todo("parse")


@app.command()
def aggregate() -> None:
    """Compute per-evaluator grade statistics from parsed theses (TODO)."""
    _todo("aggregate")


@app.command()
def build() -> None:
    """Write the static JSON aggregates served to the website (TODO)."""
    _todo("build")


if __name__ == "__main__":
    app()
