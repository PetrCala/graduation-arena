# pipeline

Python data pipeline: **scrape -> parse -> aggregate -> build** static JSON.

A [`uv`](https://docs.astral.sh/uv/) project exposing a [`typer`](https://typer.tiangolo.com/)
CLI (`ga-pipeline`) with `scrape | parse | aggregate | build` subcommands. `scrape` now contains
the A1 OAI-PMH source-access spike: it can fetch one DSpace `xoai` record or list raw IES records
and write RawThesis-shaped JSON. The later `parse | aggregate | build` stages are still stubs.

Reads theses from the public source, writes `../data/aggregates/*.json`. See
[../docs/app-architecture.md](../docs/app-architecture.md).

Planned libraries (not yet added): `httpx`, `selectolax`/BeautifulSoup,
`pdfplumber`/PyMuPDF, `pydantic`, `polars`.

Example source probe:

```bash
uv run ga-pipeline scrape --identifier oai:dspace.cuni.cz:20.500.11956/176640
uv run ga-pipeline scrape --set col_20.500.11956_1918 --limit 5 --output ../data/raw/a1.json
```

`col_20.500.11956_1918` is a broad FSV thesis collection in DSpace, so `scrape` filters listed
records to metadata containing `Institute of Economic Studies` / `Institut ekonomických studií`
by default. Use `--all-departments` only when you intentionally want the unfiltered source set.

## Layout

```
pipeline/
  pyproject.toml         # uv project: typer dep, ruff + pytest dev deps, ga-pipeline script
  src/ga_pipeline/
    __init__.py
    cli.py               # typer app with the four stage subcommands
    oai.py               # A1 OAI-PMH client + raw metadata mapper
  tests/
    test_cli.py          # smoke tests: --help lists the stages; stub stages run
    test_oai.py          # local XML tests for OAI parsing and RawThesis-shaped output
```

## Develop

Run from this directory.

```bash
uv sync               # create the venv and install deps (incl. dev)
uv run ga-pipeline --help

uv run ruff check     # lint
uv run ruff format    # format
uv run pytest         # tests
```

`uv.lock` is committed; `.venv/` is not.
