"""Smoke tests for the ga-pipeline CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from ga_pipeline.cli import app

runner = CliRunner()

SUBCOMMANDS = ("scrape", "parse", "aggregate", "build")


def test_help_lists_all_subcommands() -> None:
    """`ga-pipeline --help` exits cleanly and lists the four stages."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in SUBCOMMANDS:
        assert sub in result.stdout


def test_non_scrape_subcommands_run_and_report_todo() -> None:
    """Stub stages are still wired up and report that they are pending."""
    for sub in ("parse", "aggregate", "build"):
        result = runner.invoke(app, [sub])
        assert result.exit_code == 0, f"{sub} exited {result.exit_code}"
        assert "not implemented yet (TODO)" in result.stdout
