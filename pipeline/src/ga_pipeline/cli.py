"""Typer CLI entry point for the graduation-arena data pipeline.

Exposes the four pipeline stages as subcommands. Each is wired up and runnable
but, for now, only reports that it is not implemented yet. The real scrape /
parse / aggregate / build logic lands in later issues.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from ga_pipeline.oai import DEFAULT_METADATA_PREFIX, DEFAULT_SET_SPEC, OaiClient, OaiError

logger = logging.getLogger("ga_pipeline")

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
    identifier: Annotated[
        str | None,
        typer.Option(
            "--identifier",
            "-i",
            help="Fetch one OAI identifier, e.g. oai:dspace.cuni.cz:20.500.11956/176640.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=1, help="Maximum records for ListRecords mode."),
    ] = 10,
    set_spec: Annotated[
        str,
        typer.Option("--set", help="OAI setSpec to list when --identifier is omitted."),
    ] = DEFAULT_SET_SPEC,
    metadata_prefix: Annotated[
        str,
        typer.Option("--metadata-prefix", help="OAI metadataPrefix to request."),
    ] = DEFAULT_METADATA_PREFIX,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write JSON to this path instead of stdout."),
    ] = None,
    all_departments: Annotated[
        bool,
        typer.Option(
            "--all-departments",
            help="Do not filter the broad FSV thesis set down to Institute of Economic Studies.",
        ),
    ] = False,
) -> None:
    """Fetch raw OAI-PMH metadata from DSpace as RawThesis-shaped JSON."""
    client = OaiClient()
    try:
        if identifier:
            payload: dict | list = client.get_record(identifier, metadata_prefix).to_raw_thesis()
        else:
            payload = [
                record.to_raw_thesis()
                for record in client.list_records(
                    metadata_prefix=metadata_prefix,
                    set_spec=set_spec,
                    limit=limit,
                    ies_only=not all_departments,
                )
            ]
    except OaiError as exc:
        typer.echo(f"scrape failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        typer.echo(f"wrote {output}")


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
