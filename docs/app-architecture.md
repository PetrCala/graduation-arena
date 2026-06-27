# Application architecture (draft)

Status: **Draft** — agreed 2026-06-27. Refine as source/legal facts land.

This records the high-level shape of the application. It is intentionally a rough
direction, not a spec.

## Decisions

1. **Monorepo.** Everything lives in this repo (`graduation-arena`). The data contract is
   shared between the pipeline (producer) and the website (consumer), so a monorepo keeps
   them in lockstep — one PR can change a schema and both sides together. Revisit only if
   the site becomes its own product with a separate release cadence, or the pipeline is
   open-sourced independently.

2. **No live backend.** The dataset is read-only and refreshed in a batch roughly every six
   months, and is small (a few hundred distinct evaluators; aggregates in the KB–low-MB
   range). The pipeline precomputes aggregates to **static JSON**; the static site reads
   them and runs the supervisor + opponent lookup **client-side**. No server, no live
   database. Sits comfortably on Firebase's free tier.

3. **Storage split by role.**
   - *Processing store* (during scrape/parse; local, not deployed): SQLite or Parquet —
     resumable and inspectable.
   - *Serving store* (what the site reads): static JSON artifacts on Firebase Hosting.
   - Firestore is intentionally **not** used now. Revisit only if the data grows large or
     needs live queries/writes.

## Stack

| Layer | Choice |
| --- | --- |
| Pipeline | Python (`uv`); `httpx`, `selectolax`/BeautifulSoup, `pdfplumber`/PyMuPDF, `pydantic`, `polars`; `typer` CLI |
| Schemas (contract) | `pydantic` source → generated JSON Schema → generated TypeScript types |
| Serving store | Static JSON on Firebase Hosting |
| Web | SvelteKit (static adapter) + Tailwind |
| CI/CD | GitHub Actions: deploy on merge; scheduled ~6-month data refresh |

The frontend is SvelteKit (static adapter) because the app is interactive — two inputs and
live client-side filtering — which fits SvelteKit better than a content-first tool. Easy to
revisit while still scaffolding.

## Contract glue

The schema is single-sourced in **pydantic**. JSON Schema and the TypeScript types consumed
by the web app are **generated** from it, never hand-written — so producer and consumer
cannot drift.

```
pydantic models  ──exports──►  JSON Schema  ──generates──►  TypeScript types
   (pipeline)                                                    (web)
```

## Data flow

```
   ┌─ GH Actions cron (~6mo)  or  local CLI ─┐
   │   Python pipeline:                       │
   │   scrape → parse → aggregate             │
   └───────────────┬──────────────────────────┘
                   │ writes
            data/aggregates/*.json   (tiny, static)
                   │ bundled at build
   ┌───────────────┴──────────────────────────┐
   │   GH Actions on push: build static site   │
   └───────────────┬──────────────────────────┘
                   │ deploy
            Firebase Hosting  ──►  student visits,
                                   supervisor + opponent
                                   lookup runs client-side
```

## Repository layout

```
graduation-arena/
  pipeline/      # python: scraper, parser, aggregation + typer CLI
  web/           # typescript static site (SvelteKit)
  schemas/       # shared contract: pydantic source + generated TS types
  data/
    fixtures/    # sample pages/PDFs + example aggregate JSON
    aggregates/  # pipeline output (static JSON served to the site)
  .github/workflows/   # deploy + refresh (added later)
  docs/
```

## Deferred decisions

- **Final schema fields** — pending the source-access spike + real fixtures (A1) and the
  legal verdict on naming vs. anonymising/aggregating evaluators. A provisional `v0` draft
  comes first (K2).
- **`data/aggregates/`** — commit to git vs. produce as a build artifact. TBD.
- **Firestore** — only if data size or live-query needs outgrow static JSON.
