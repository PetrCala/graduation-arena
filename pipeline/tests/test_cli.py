"""Smoke tests for the ga-pipeline CLI."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from io import BytesIO

import pytest
from ga_schemas.models import (
    Evaluator,
    EvaluatorRole,
    EvaluatorStats,
    Level,
    ParsedThesis,
    RawThesis,
)
from typer.testing import CliRunner

from ga_pipeline.cli import app
from ga_pipeline.parser import ParseSkipError, parse_raw_thesis
from ga_pipeline.store import ProcessingStore

runner = CliRunner()

SUBCOMMANDS = ("scrape", "parse", "aggregate", "build")


def test_help_lists_all_subcommands() -> None:
    """`ga-pipeline --help` exits cleanly and lists the four stages."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in SUBCOMMANDS:
        assert sub in result.stdout


def test_parse_writes_valid_parsed_records(tmp_path) -> None:
    """The parse command normalises stored raw theses into SQLite parsed rows."""
    store = tmp_path / "processing.sqlite"
    with ProcessingStore(store) as processing_store:
        processing_store.upsert_raw_thesis(_raw_thesis("1", grade="Very good"))
        processing_store.upsert_raw_thesis(_raw_thesis("2", grade=None))

    result = runner.invoke(app, ["parse", "--store", str(store)])

    assert result.exit_code == 0, result.output
    assert "stored 1 parsed thesis record(s), skipped 1" in result.stdout
    with sqlite3.connect(store) as connection:
        row = connection.execute("SELECT parsed_json FROM parsed_theses").fetchone()

    assert row is not None
    assert '"defense_grade":2' in row[0]
    assert '"language":"en"' in row[0]
    assert '"role":"supervisor"' in row[0]


def test_parse_handles_en_language_and_first_opponent() -> None:
    """Parser accepts EN records and uses the first referee when multiple are present."""
    thesis = parse_raw_thesis(
        _raw_thesis(
            "3",
            language="en_US",
            opponent=("Opponent, First", "Opponent, Second"),
            grade="C",
        )
    )

    assert thesis.language == "en"
    assert thesis.level == "bachelor"
    assert thesis.defense_grade == 2
    assert thesis.opponent.name == "Opponent, First"
    assert thesis.opponent.id == "opponent-first"


def test_parse_skips_defended_records_missing_grade() -> None:
    """Defended theses without a grade are excluded instead of silently emitted."""
    with pytest.raises(ParseSkipError, match="missing a parseable grade"):
        parse_raw_thesis(_raw_thesis("4", grade=None))


def test_scrape_harvests_oai_records_into_sqlite(tmp_path, monkeypatch) -> None:
    """The scrape command follows OAI pages and upserts raw records into SQLite."""
    pages = [_oai_page("token-2", "176640"), _oai_page(None, "176641")]
    requested_urls: list[str] = []

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202 - stdlib test double
        requested_urls.append(request.full_url)
        return _Response(pages.pop(0).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    store = tmp_path / "processing.sqlite"
    result = runner.invoke(
        app,
        [
            "scrape",
            "--store",
            str(store),
            "--from",
            "2024-01-01",
            "--until",
            "2024-12-31",
            "--delay-seconds",
            "0",
            "--contact-email",
            "research@example.test",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "stored 2 raw thesis record(s)" in result.stdout
    assert "from=2024-01-01" in requested_urls[0]
    assert "until=2024-12-31" in requested_urls[0]
    assert "resumptionToken=token-2" in requested_urls[1]

    with sqlite3.connect(store) as connection:
        rows = connection.execute(
            "SELECT source_id, source_url, raw_fields_json FROM raw_theses ORDER BY source_id"
        ).fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "oai:dspace.cuni.cz:20.500.11956/176640"
    assert rows[0][1] == "https://dspace.cuni.cz/handle/20.500.11956/176640"
    assert "advisor" in rows[0][2]


def test_aggregate_writes_probabilities_and_gates_small_groups(tmp_path) -> None:
    """Aggregate emits only min-N evaluators and normalises grade probabilities."""
    store = tmp_path / "processing.sqlite"
    with ProcessingStore(store) as processing_store:
        processing_store.replace_parsed_theses(
            [
                (
                    "raw-1",
                    _parsed_thesis(
                        "1", supervisor="Public, Pat", opponent="Private, Pia", grade=1
                    ),
                ),
                (
                    "raw-2",
                    _parsed_thesis(
                        "2", supervisor="Public, Pat", opponent="Other, Oli", grade=2
                    ),
                ),
                (
                    "raw-3",
                    _parsed_thesis(
                        "3", supervisor="Private, Pia", opponent="Other, Oli", grade=3
                    ),
                ),
            ]
        )

    result = runner.invoke(app, ["aggregate", "--store", str(store), "--min-n", "2"])

    assert result.exit_code == 0, result.output
    assert "stored 3 evaluator stat record(s) with min-n 2" in result.stdout
    with ProcessingStore(store) as processing_store:
        stats = list(processing_store.iter_evaluator_stats())

    by_name = {stat.evaluator.name: stat for stat in stats}
    assert set(by_name) == {"Public, Pat", "Private, Pia", "Other, Oli"}
    for stat in stats:
        assert sum(stat.grade_probabilities.values()) == pytest.approx(1.0)

    pat = by_name["Public, Pat"]
    assert pat.grade_distribution == {"1": 1, "2": 1}
    assert pat.grade_probabilities == {"1": 0.5, "2": 0.5}
    assert pat.by_role == {"supervisor": {"1": 1, "2": 1}}
    assert pat.by_level == {"bachelor": {"2": 1}, "master": {"1": 1}}


def test_aggregate_withholds_below_min_n_evaluators(tmp_path) -> None:
    """Evaluators below the configured served threshold are not emitted."""
    store = tmp_path / "processing.sqlite"
    with ProcessingStore(store) as processing_store:
        processing_store.replace_parsed_theses(
            [
                (
                    "raw-1",
                    _parsed_thesis("1", supervisor="Kept, Kim", opponent="Hidden, Hal", grade=1),
                ),
                (
                    "raw-2",
                    _parsed_thesis("2", supervisor="Kept, Kim", opponent="Other, Ora", grade=2),
                ),
            ]
        )

    result = runner.invoke(app, ["aggregate", "--store", str(store), "--min-n", "2"])

    assert result.exit_code == 0, result.output
    with ProcessingStore(store) as processing_store:
        stats = list(processing_store.iter_evaluator_stats())

    assert [stat.evaluator.name for stat in stats] == ["Kept, Kim"]


def test_build_writes_static_evaluator_stats_json(tmp_path) -> None:
    """Build writes the served static JSON artifact from stored aggregate rows."""
    store = tmp_path / "processing.sqlite"
    output_dir = tmp_path / "aggregates"
    with ProcessingStore(store) as processing_store:
        processing_store.replace_evaluator_stats(
            [
                EvaluatorStats(
                    evaluator=Evaluator(name="Public, Pat", id="public-pat"),
                    total_theses=2,
                    grade_distribution={"1": 1, "2": 1},
                    grade_probabilities={"1": 0.5, "2": 0.5},
                    last_updated=datetime(2026, 6, 27, tzinfo=UTC).date(),
                )
            ]
        )

    result = runner.invoke(
        app,
        ["build", "--store", str(store), "--output-dir", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    output = output_dir / "evaluator-stats.json"
    assert output.exists()
    assert '"name": "Public, Pat"' in output.read_text(encoding="utf-8")


class _Response(BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self.close()


def _oai_page(token: str | None, handle: str) -> str:
    token_xml = f"<resumptionToken>{token}</resumptionToken>" if token else "<resumptionToken />"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:dspace.cuni.cz:20.500.11956/{handle}</identifier>
        <datestamp>2024-06-01</datestamp>
        <setSpec>col_20.500.11956_1918</setSpec>
      </header>
      <metadata>
        <xoai xmlns="http://www.lyncode.com/xoai">
          <element name="contributor">
            <element name="advisor">
              <field name="value">doc. Test Advisor</field>
            </element>
          </element>
        </xoai>
      </metadata>
    </record>
  {token_xml}
  </ListRecords>
</OAI-PMH>
"""


def _raw_thesis(
    source_suffix: str,
    *,
    language: str = "en_US",
    opponent: tuple[str, ...] = ("Opponent, Ola",),
    grade: str | None = "Excellent",
) -> RawThesis:
    grade_values = () if grade is None else (grade,)
    return RawThesis(
        source_id=f"oai:dspace.cuni.cz:20.500.11956/{source_suffix}",
        source_url=f"https://dspace.cuni.cz/handle/20.500.11956/{source_suffix}",
        fetched_at=datetime(2026, 6, 27, tzinfo=UTC),
        raw_fields={
            "metadata": _node(
                children=[
                    _branch(
                        "dc",
                        _branch(
                            "contributor",
                            _branch("advisor", _values("Advisor, Alice")),
                            _branch("referee", _values(*opponent)),
                        ),
                        _branch("creator", _values("Student, Stan")),
                        _branch("date", _branch("issued", _values("2024"))),
                        _branch(
                            "description",
                            _branch(
                                "department",
                                _values(
                                    "Institut ekonomických studií",
                                    wrapper_names=("cs_CZ",),
                                ),
                            ),
                            _branch("abstract", _values("An abstract.", wrapper_names=("en_US",))),
                        ),
                        _branch("language", _branch("iso", _values(language))),
                        _branch("title", _values("A Thesis Title", wrapper_names=("en_US",))),
                    ),
                    _branch(
                        "thesis",
                        _branch("degree", _branch("name", _values("Bc."))),
                        _branch("grade", _values(*grade_values)),
                    ),
                    _branch("uk", _branch("thesis", _branch("defenceStatus", _values("O")))),
                ]
            )
        },
    )


def _parsed_thesis(
    suffix: str,
    *,
    supervisor: str,
    opponent: str,
    grade: int,
) -> ParsedThesis:
    return ParsedThesis(
        id=f"parsed-{suffix}",
        title=f"Thesis {suffix}",
        author="Student, Stan",
        year=2024,
        level=Level.master if int(suffix) % 2 else Level.bachelor,
        language="en",
        supervisor=Evaluator(
            name=supervisor,
            id=supervisor.lower().replace(", ", "-"),
            role=EvaluatorRole.supervisor,
        ),
        opponent=Evaluator(
            name=opponent,
            id=opponent.lower().replace(", ", "-"),
            role=EvaluatorRole.opponent,
        ),
        defense_grade=grade,
        source_url=f"https://example.test/{suffix}",
    )


def _branch(name: str, *children: dict) -> dict:
    return _node(name=name, children=list(children))


def _values(*values: str, wrapper_names: tuple[str, ...] = ("none",)) -> dict:
    return _node(
        name=wrapper_names[0],
        children=[_node(tag="field", name="value", text=value) for value in values],
    )


def _node(
    *,
    tag: str = "element",
    name: str | None = None,
    text: str | None = None,
    children: list[dict] | None = None,
) -> dict:
    node: dict = {"tag": tag}
    if name is not None:
        node["attrs"] = {"name": name}
    if text is not None:
        node["text"] = text
    if children is not None:
        node["children"] = children
    return node
