"""Smoke tests for the ga-pipeline CLI skeleton."""

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


def test_each_subcommand_runs_and_reports_todo() -> None:
    """Every stage is wired up, runs, and reports it is not implemented yet."""
    for sub in SUBCOMMANDS:
        result = runner.invoke(app, [sub])
        assert result.exit_code == 0, f"{sub} exited {result.exit_code}"
        assert "not implemented yet (TODO)" in result.stdout
