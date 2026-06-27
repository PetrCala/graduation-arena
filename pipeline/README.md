# pipeline

Python data pipeline: **scrape → parse → aggregate → build** static JSON.

A [`uv`](https://docs.astral.sh/uv/) project exposing a [`typer`](https://typer.tiangolo.com/)
CLI (`ga-pipeline`) with `scrape | parse | aggregate | build` subcommands. The stages are
currently **stubs** — wired up and runnable, but each only reports `not implemented yet
(TODO)`. The real scraping/parsing/aggregation logic lands in later issues.

Reads theses from the public source, writes `../data/aggregates/*.json`. See
[../docs/app-architecture.md](../docs/app-architecture.md).

Planned libraries (not yet added): `httpx`, `selectolax`/BeautifulSoup,
`pdfplumber`/PyMuPDF, `pydantic`, `polars`.

## Layout

```
pipeline/
  pyproject.toml         # uv project: typer dep, ruff + pytest dev deps, ga-pipeline script
  src/ga_pipeline/
    __init__.py
    cli.py               # typer app with the four stage subcommands
  tests/
    test_cli.py          # smoke tests: --help lists the stages; each stage runs
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

<!-- ci-smoke-test: throwaway change to verify the pipeline CI gate triggers; do not merge -->
