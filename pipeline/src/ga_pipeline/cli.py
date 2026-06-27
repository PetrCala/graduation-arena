"""Typer CLI entry point for the graduation-arena data pipeline."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from ga_schemas.models import Evaluator, EvaluatorRole, EvaluatorStats, ParsedThesis

from ga_pipeline.oai import DEFAULT_SET_SPEC, HarvestConfig, OAIClient
from ga_pipeline.parser import ParseSkipError, parse_raw_thesis
from ga_pipeline.store import ProcessingStore

logger = logging.getLogger("ga_pipeline")
PIPELINE_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = PIPELINE_DIR.parent
DEFAULT_STORE = PIPELINE_DIR.parent / "local" / "processing.sqlite"
DEFAULT_AGGREGATES_DIR = REPO_DIR / "data" / "aggregates"
DEFAULT_MIN_N = 5

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
def parse(
    store: Annotated[
        Path,
        typer.Option(
            "--store",
            help="SQLite processing store to read raw records from and write parsed records into.",
        ),
    ] = DEFAULT_STORE,
    include_non_ies: Annotated[
        bool,
        typer.Option(
            "--include-non-ies",
            help=(
                "Parse every raw record instead of filtering to Institute of Economic "
                "Studies theses."
            ),
        ),
    ] = False,
) -> None:
    """Normalise scraped theses into structured parsed records."""
    parsed = []
    skipped = 0
    with ProcessingStore(store) as processing_store:
        for raw_thesis in processing_store.iter_raw_theses():
            try:
                parsed.append(
                    (
                        raw_thesis.source_id,
                        parse_raw_thesis(raw_thesis, require_ies=not include_non_ies),
                    )
                )
            except ParseSkipError as exc:
                skipped += 1
                logger.debug("skipping %s: %s", raw_thesis.source_id, exc)
        processing_store.replace_parsed_theses(parsed)

    typer.echo(f"parse: stored {len(parsed)} parsed thesis record(s), skipped {skipped}")


@app.command()
def aggregate(
    store: Annotated[
        Path,
        typer.Option(
            "--store",
            help="SQLite processing store to read parsed records from and write stats into.",
        ),
    ] = DEFAULT_STORE,
    min_n: Annotated[
        int,
        typer.Option(
            "--min-n",
            min=1,
            envvar="GA_MIN_EVALUATOR_THESES",
            help="Minimum graded thesis count required before an evaluator is served.",
        ),
    ] = DEFAULT_MIN_N,
) -> None:
    """Compute public per-evaluator grade statistics from parsed theses."""
    with ProcessingStore(store) as processing_store:
        stats = aggregate_evaluator_stats(processing_store.iter_parsed_theses(), min_n=min_n)
        processing_store.replace_evaluator_stats(stats)

    typer.echo(f"aggregate: stored {len(stats)} evaluator stat record(s) with min-n {min_n}")


@app.command()
def build(
    store: Annotated[
        Path,
        typer.Option(
            "--store",
            help="SQLite processing store to read aggregated evaluator stats from.",
        ),
    ] = DEFAULT_STORE,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory for static JSON aggregate artifacts.",
        ),
    ] = DEFAULT_AGGREGATES_DIR,
) -> None:
    """Write the static JSON aggregates served to the website."""
    with ProcessingStore(store) as processing_store:
        stats = list(processing_store.iter_evaluator_stats())

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evaluator-stats.json"
    output_path.write_text(
        json.dumps(
            [stat.model_dump(mode="json", exclude_none=True) for stat in stats],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    typer.echo(f"build: wrote {len(stats)} evaluator stat record(s) to {output_path}")


def aggregate_evaluator_stats(
    theses: Iterable[ParsedThesis],
    *,
    min_n: int = DEFAULT_MIN_N,
    today: date | None = None,
) -> list[EvaluatorStats]:
    """Roll parsed thesis rows into served evaluator statistics."""
    grouped: dict[str, _EvaluatorAccumulator] = {}
    for thesis in theses:
        if thesis.defense_grade is None:
            continue
        _accumulate_evaluator(grouped, thesis.supervisor, EvaluatorRole.supervisor, thesis)
        _accumulate_evaluator(grouped, thesis.opponent, EvaluatorRole.opponent, thesis)

    last_updated = today or date.today()
    stats = [
        accumulator.to_stats(last_updated)
        for accumulator in grouped.values()
        if accumulator.total >= min_n
    ]
    return sorted(stats, key=lambda stat: (stat.evaluator.name.casefold(), stat.evaluator.id or ""))


class _EvaluatorAccumulator:
    def __init__(self, evaluator: Evaluator) -> None:
        self.evaluator = Evaluator(name=evaluator.name, id=evaluator.id)
        self.grades: Counter[str] = Counter()
        self.by_role: dict[str, Counter[str]] = defaultdict(Counter)
        self.by_level: dict[str, Counter[str]] = defaultdict(Counter)

    @property
    def total(self) -> int:
        return sum(self.grades.values())

    def add(self, role: EvaluatorRole, thesis: ParsedThesis) -> None:
        grade = str(thesis.defense_grade)
        self.grades[grade] += 1
        self.by_role[role.value][grade] += 1
        self.by_level[thesis.level.value][grade] += 1

    def to_stats(self, last_updated: date) -> EvaluatorStats:
        total = self.total
        return EvaluatorStats(
            evaluator=self.evaluator,
            total_theses=total,
            grade_distribution=_sorted_counts(self.grades),
            grade_probabilities={
                grade: count / total for grade, count in _sorted_counts(self.grades).items()
            },
            by_role={role: _sorted_counts(counts) for role, counts in sorted(self.by_role.items())},
            by_level={
                level: _sorted_counts(counts) for level, counts in sorted(self.by_level.items())
            },
            last_updated=last_updated,
        )


def _accumulate_evaluator(
    grouped: dict[str, _EvaluatorAccumulator],
    evaluator: Evaluator,
    role: EvaluatorRole,
    thesis: ParsedThesis,
) -> None:
    key = evaluator.id or evaluator.name.casefold()
    grouped.setdefault(key, _EvaluatorAccumulator(evaluator)).add(role, thesis)


def _sorted_counts(counts: Counter[str]) -> dict[str, int]:
    return {grade: counts[grade] for grade in sorted(counts)}


if __name__ == "__main__":
    app()
