# pipeline

Python data pipeline: **scrape → parse → aggregate → build** static JSON.

To be initialised in the tooling-baseline issue (K1) as a `uv` project exposing a `typer`
CLI with `scrape | parse | aggregate | build` subcommands.

Planned libraries: `httpx`, `selectolax`/BeautifulSoup, `pdfplumber`/PyMuPDF, `pydantic`,
`polars`.

Reads theses from the public source, writes `../data/aggregates/*.json`. See
[../docs/app-architecture.md](../docs/app-architecture.md).
