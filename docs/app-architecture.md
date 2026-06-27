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
   - *Processing store* (during scrape/parse; local, not deployed): **SQLite**. A single
     relational file gives row-level upsert/dedupe on `source_id`, resumable/incremental
     (`--from`/`--until`) harvests, and SQL inspection — the right fit for a stage that
     mutates rows. polars reads it directly for aggregation. (Parquet was considered but is
     append-oriented and awkward for the row-level dedupe/resume the harvest needs.)
   - *Serving store* (what the site reads): static JSON artifacts on Firebase Hosting.
   - *Serving artifacts* (`data/aggregates/*.json`) are **produced as a CI build artifact,
     not committed to git** — `data/aggregates/` is git-ignored. These are per-evaluator
     grade profiles (personal data); keeping them out of the public repo avoids publishing
     personal data into permanent git history. What ships must be the GDPR-safe served
     projection (min-N gating, no student names — #18) and is gated by the legal go/no-go
     (#14).
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
            data/aggregates/*.json   (tiny, static; CI build artifact, git-ignored)
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
    aggregates/  # pipeline output (static JSON; CI build artifact, git-ignored)
  .github/workflows/   # deploy + refresh (added later)
  docs/
```

## Deferred decisions

- **Final schema fields** — pending the source-access spike + real fixtures (A1). A
  provisional `v0` draft comes first (K2). The legal verdict is **decided (X1, #14):
  proceed with the public site and name evaluators** — the schema keeps named,
  person-linkable evaluators, subject to the served-boundary safeguards in #18 (min-N
  gating, no student names served, opt-out).
- **Firestore** — only if data size or live-query needs outgrow static JSON.
