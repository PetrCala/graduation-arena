"""Typer CLI entry point for the graduation-arena data pipeline.

Exposes the four pipeline stages as subcommands. Each is wired up and runnable
but, for now, only reports that it is not implemented yet. The real scrape /
parse / aggregate / build logic lands in later issues.
"""

from __future__ import annotations

import logging

import typer

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
def scrape() -> None:
    """Fetch raw theses from the public source (TODO)."""
    _todo("scrape")


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
