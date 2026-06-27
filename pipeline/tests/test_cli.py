"""Smoke tests for the ga-pipeline CLI."""

from __future__ import annotations

import sqlite3
from io import BytesIO

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


def test_unimplemented_subcommands_report_todo() -> None:
    """The later stages remain wired up while their implementations are deferred."""
    for sub in ("parse", "aggregate", "build"):
        result = runner.invoke(app, [sub])
        assert result.exit_code == 0, f"{sub} exited {result.exit_code}"
        assert "not implemented yet (TODO)" in result.stdout


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
