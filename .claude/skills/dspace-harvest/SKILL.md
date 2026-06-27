---
name: dspace-harvest
description: >-
  Playbook for harvesting IES thesis records from Charles University's DSpace
  repository (dspace.cuni.cz) — which endpoint to use (OAI-PMH `xoai`/`dim` vs
  REST vs sitemap), why `oai_dc` silently drops the grade, robots.txt limits,
  rate/politeness rules, the per-record field set, and the two grade scales.
  Use when writing, debugging, or reviewing the harvester/scraper, when
  enumerating or fetching theses, or when parsing supervisor/opponent/grade
  metadata from dspace.cuni.cz.
---

# Harvesting IES theses from DSpace

Actionable playbook for the harvest layer. Full background lives in
[`docs/data-source.md`](../../../docs/data-source.md) and
[`docs/architecture-report.md`](../../../docs/architecture-report.md) (§1, §2.1). This skill is the
distilled "do this, not that".

## Source of truth: `dspace.cuni.cz` (DSpace 6.4)

Target the **public Charles University DSpace** repository — nothing else.

| Do **not** target | Why |
| --- | --- |
| `is.cuni.cz` (SIS) | Login-gated (CAS). Not a scrape target. |
| `ies.fsv.cuni.cz` | Just a landing page that hands off to pre-filtered DSpace searches. |
| `theses.cz` | Secondary national mirror; DSpace is the authoritative CU copy. |

- IES theses sit under the **FSV community**, collection **Institut ekonomických studií**, collection
  handle `20.500.11956/1918`.
- Everything the MVP needs is public, anonymous, and machine-readable. **No login, and no PDF parsing
  for the happy path.**

## Enumerate via OAI-PMH or the sitemap — never the search UI

`robots.txt` disallows `/discover`, `/browse`, `/search-filter`, `/statistics`, and fully bans
mirroring tools (`wget`, `HTTrack`, …). It **allows** per-item `/handle/...` pages, `/bitstream/...`,
and the APIs.

➡ **Enumerate with OAI-PMH `ListRecords` (or the sitemap). Do not crawl `/discover` or `/browse`.**

## Pick the right metadata format (this is the easy mistake)

OAI-PMH base: `https://dspace.cuni.cz/oai/request`

| Format | Use it? |
| --- | --- |
| `oai_dc` | ❌ **Omits the grade** and collapses advisor/opponent/consultant into undifferentiated `dc:contributor`. |
| `xoai` / `dim` | ✅ Full field set, including the grade and role-tagged names (the custom `uk.*` thesis fields). |

- FSV set: `setSpec=com_20.500.11956_1905`.
- Incremental harvest: `from` / `until` datestamps + resumption tokens.
- **Verify before building:** run one `GetRecord&metadataPrefix=xoai` against a known record and
  confirm the grade and role-tagged names are actually present.

## Endpoints (verified 2026-06-27)

- **OAI-PMH:** `https://dspace.cuni.cz/oai/request?verb=Identify` (formats: `oai_dc`, `xoai`, `dim`, …)
- **REST (DSpace 6):** `https://dspace.cuni.cz/rest` — `/rest/status` (→ `sourceVersion 6.4`),
  `/rest/handle/20.500.11956/1918`, `/rest/collections/{id}/items`, `/rest/items/{id}/bitstreams`.
  ⚠ The DSpace 7 path `/server/api` returns **404** — it is not deployed; don't use it.
- **Item page:** `https://dspace.cuni.cz/handle/20.500.11956/<id>`; bitstreams under
  `/bitstream/handle/...`.
- **Sitemap (robots-blessed enumeration):** `https://dspace.cuni.cz/sitemap`.
- **Example record for tests:** `https://dspace.cuni.cz/handle/20.500.11956/206686`.

## Fields each record exposes (structured — MVP needs no PDF)

Title (cs/en), author (student), defense date, **supervisor** (vedoucí), **opponent**
(referee / oponent), consultant, department, degree level, program, discipline, language, defense
status (`DEFENDED` / `OBHÁJENO` vs not defended), and the **final defense grade**.

PDF bitstreams (Phase 2 only): full text, `posudek vedoucího`, `posudek oponenta`, `záznam o průběhu
obhajoby`. Do not parse PDFs for the happy path.

## Two grade scales — keep them separate

1. **Final defense grade** (in metadata; the thing to predict): `1 = výborně`, `2 = velmi dobře`,
   `3 = dobře`, `4 = neprospěl/a`. Normalize to ordinal `1..4`.
2. **Proposed grades in IES posudky** (PDF, Phase 2): letters `A–F` backed by `0–100` points.

⚠ The `A–F` ↔ `1–4` mapping is **unofficial** — the committee sets the final grade independently, it
is not a copy of either proposal. Treat the mapping as reviewable config, never a hardcoded
equivalence.

## Politeness (non-negotiable)

- Send a descriptive `User-Agent` with a contact email.
- Self-impose **≥1–2 s between requests**; named crawlers are held to `crawl-delay: 30`. Prefer bulk
  OAI harvest with datestamp windows over page-by-page fetching.
- Validate every harvested record with a **pydantic** model; fail loudly on schema drift.
- **Non-commercial use only** (Rector's Decree 13/2017). No ads, no paywall.

> Legal note: names plus grade histories of named examiners are personal data, and aggregating them
> is profiling under GDPR. The *harvest* itself is pure engineering, but anything *served* must
> respect the safeguards in [`docs/architecture-report.md`](../../../docs/architecture-report.md) §6
> (min-N gating, no student names, opt-out). Don't design serving behavior here without reading that
> section.
