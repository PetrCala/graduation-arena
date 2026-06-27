# Data-harvesting pipeline — design sketch

Status: **Sketch** — drafted 2026-06-27. High-level direction only, *no implementation code*.
Builds on the verified facts in [data-source.md](data-source.md) and the shape in
[app-architecture.md](app-architecture.md). Expect fields and module boundaries to firm up
after the source-access spike (A1) and real fixtures land.

This note answers one question: **how do we turn a few thousand public DSpace records into a
tiny, structured grades dataset — without hoarding PDFs?**

---

## 0. The central principle — boil down, don't hoard

> **Never store whole documents when a handful of fields is all the product uses.**

The prediction website needs, per thesis, essentially six fields: *supervisor, opponent,
final grade, year, degree level, language*. **All six live in the record metadata.** So:

1. **The MVP predictor needs zero PDFs.** Harvest metadata via OAI-PMH/REST and you already
   have the full happy-path signal.
2. **The full-text thesis PDF is never downloaded** for grade analysis (fetch on demand only,
   if ever — e.g. a future abstract-based feature).
3. **The only PDFs worth touching are the two `posudky`** (supervisor + opponent reports),
   and only to extract a tiny per-evaluator record:
   `{role, proposed_grade, points_total, points_breakdown?}`. **After extraction, discard the
   PDF bytes** — keep only the extracted JSON plus a source URL + checksum for provenance and
   re-extraction. PDFs are *transient inputs*, not storage.

Everything below is in service of this principle.

---

## 1. Source & enumeration

**Primary source:** Charles University DSpace repository, `dspace.cuni.cz` (DSpace 6.4).
Not the IES website, not SIS (`is.cuni.cz` is login-gated — never target it).

IES corpus: a few thousand records under the FSV community, department
`Institut ekonomických studií`, IES collection handle `20.500.11956/1918`, work types
`bakalářská` / `diplomová` / `rigorózní` / `dizertační práce`. Small data.

### Enumeration routes, in order of preference

1. **OAI-PMH — preferred bulk harvest.** `https://dspace.cuni.cz/oai/request`
   - Verbs: `Identify` (sanity check), `ListRecords` (bulk), `GetRecord` (single, for spikes).
   - **Metadata format: `xoai` or `dim`** — these expose the role-tagged names and the grade
     and custom `uk.*` fields. `oai_dc` is **not enough**: it drops the grade and collapses
     advisor/opponent/consultant into undifferentiated `dc:contributor`.
   - **Set scoping:** harvest the IES collection set rather than the whole FSV community if a
     per-collection set exists (likely `col_20.500.11956_1918`). FSV community set is
     `com_20.500.11956_1905` as a fallback, filtered to IES in the mapper. *Verify the exact
     set spec before building (open question Q1).*
   - **Incremental:** use `from` / `until` datestamps + `resumptionToken` paging for the
     bi-annual refresh — harvest only what changed since the last watermark.

2. **REST API (DSpace 6) — secondary / targeted.** `https://dspace.cuni.cz/rest`
   - `/rest/handle/20.500.11956/1918`, `/rest/collections/{id}/items`,
     `/rest/items/{id}/bitstreams`.
   - Use to **list and locate bitstreams** for a record (Phase 2) and to fill any gaps OAI
     leaves. (`/server/api` is 404 — there is no DSpace 7.)

3. **Sitemap — tertiary / cross-check.** `https://dspace.cuni.cz/sitemap` to reconcile the
   harvested set against the published item list and catch anything OAI misses.

### Hard "do not" from robots.txt

- **Never crawl `/discover`, `/search-filter`, `/browse`, `/statistics`, `/login`** — all
  disallowed. Enumerate via OAI-PMH (or sitemap), never via the browse/search UI.
- Item pages `/handle/20.500.11956/...` and `/bitstream/...` **are allowed** — these are the
  only HTML/PDF endpoints we touch.

---

## 2. Two-tier extraction strategy

### Tier 1 — Metadata-only (MVP, ships first)

OAI-PMH `xoai`/`dim` → structured record. Yields supervisor, opponent, final defense grade,
defense date/year, degree level, language, title, author, abstract, keywords, status. **This
alone powers the supervisor + opponent grade predictor.** No PDF fetched.

Fallback for a missing/garbled grade: the `Záznam o průběhu obhajoby` (defense record)
bitstream may carry it — but treat as an exception path, not the norm.

### Tier 2 — Posudek-PDF enhancement (Phase 2, optional signal)

The *only* thing PDFs add is each evaluator's **proposed grade** (vs. the committee's final
grade). For each record, select **only** the two posudek bitstreams, extract a minimal record,
then throw the bytes away. See §3 for the funnel.

This tier is additive — the site works without it; it sharpens predictions when present.

---

## 3. Posudek extraction funnel (Tier 2 detail)

Per posudek PDF, escalate only as far as needed. Record `extraction_method` and `confidence`
on every result so low-confidence rows can be audited or excluded from aggregates.

```
(a) FORM-TYPE DETECTION / ROUTING
      sniff layout → IES English rubric (A–F)  vs  older FSV Czech (1–4)
                ↓
(b) TARGETED REGEX EXTRACTION  (anchored to the known form layout)
      IES: "GRADE (A – B – C – D – E – F): X"  + points table
           Contribution(30) / Methods(30) / Literature(20) / Manuscript Form(20) → TOTAL(100)
      FSV: "NAVRHOVANÁ ZNÁMKA" 1–4 line
                ↓  (text layer missing / garbled)
(c) OCR FALLBACK  for scanned / older PDFs, then retry (b)
                ↓  (messy long tail still unparsed)
(d) LLM-ASSISTED EXTRACTION  (Claude, strict JSON schema)  → low/medium confidence flag
```

Output per evaluator (the *only* thing kept):

```
{ role: "supervisor" | "opponent",
  proposed_grade,                # normalised — see §4
  points_total?,                 # IES rubric only
  points_breakdown?,             # {contribution, methods, literature, manuscript_form}
  source_url, checksum,          # provenance → re-extract later without re-storing the PDF
  extraction_method, confidence }
```

---

## 4. Normalization

- **Final defense grade:** Czech 4-point words → ordinal.
  `1 výborně` / `2 velmi dobře` / `3 dobře` / `4 neprospěl(a)`. Map both Czech and English
  labels ("Very good") to one canonical scale.
- **Proposed grade scale reconciliation:** posudky use **two scales** —
  IES English **A–F** vs. older FSV Czech **1–4**. Define one canonical target and an
  explicit, documented A–F ↔ 1–4 crosswalk (this mapping is *unofficial* — flag it as an
  assumption, open question Q3).
- **Evaluator identity resolution:** collapse name variants to one person — titles
  (`Mgr.`, `Ph.D.`), diacritics, `Surname, First` vs `First Surname`, maiden names. **Prefer
  any stable authority ID** exposed in `dim`/`xoai` over string matching (open question Q2).
- Defense date → year; degree program/discipline → degree level (Bc./Mgr./…).

---

## 5. High-level pipeline steps

```
enumerate            OAI-PMH ListRecords (xoai/dim) over the IES set, with resumption tokens
   ↓                 (incremental: from/until datestamps since last watermark)
map metadata         xoai/dim XML → RawThesis (role-tagged names, grade, dates, language)
   ↓
[Tier 1 done]        RawThesis already carries the full MVP signal
   ↓                 ── Phase 2 only, below ──
select bitstreams    via REST: keep ONLY posudek vedoucího + posudek oponenta
   ↓                 (never the full-text thesis PDF)
extract posudky      funnel §3 → minimal per-evaluator record, then DISCARD pdf bytes
   ↓
normalize            §4 — grade scales, A–F↔1–4 crosswalk, evaluator identity, year/level
   ↓
store                processing store (SQLite) → later aggregated to static JSON
```

Maps onto the existing `scrape | parse | aggregate | build` CLI:
*enumerate + map + select + extract* ≈ `scrape`/`parse`; *normalize* feeds `aggregate`.

---

## 6. Politeness / robots / legal constraints (encode in the harvester)

- **Non-commercial use only** (Rector's Decree 13/2017). This dataset and site are
  non-commercial; record that constraint where it matters.
- **Descriptive User-Agent + contact email** on every request, so the repository operator can
  reach us.
- **Rate limit ~1 request / 2s**; honour the robots `crawl-delay: 30` for any named-bot HTML/
  PDF fetching. Prefer **bulk OAI harvest** over page-by-page crawling — it sidesteps the
  per-page delay and is gentler on the server.
- **Skip all disallowed paths** (`/discover`, `/browse`, `/search-filter`, `/statistics`,
  `/login`); the site bans mirroring tools (wget/HTTrack) — we are not one.
- **Resumable + idempotent**: checkpoint the OAI resumption token and a per-record checksum so
  a refresh re-fetches only what changed and never duplicates work.

---

## 7. Module / responsibility layout (stub — names only)

| Module | One-line responsibility |
| --- | --- |
| `enumerator` | Drive OAI-PMH `ListRecords` (set + datestamps + resumption tokens); yield record ids. |
| `oai_client` | Thin polite HTTP client (UA, contact, rate limit, retries, checkpointing). |
| `metadata_mapper` | `xoai`/`dim` XML → `RawThesis` with role-tagged advisor/opponent + grade. |
| `bitstream_selector` | Per record, pick **only** the two posudek bitstreams via REST; ignore the rest. |
| `posudek_extractor` | Run the §3 funnel (route → regex → OCR → LLM); emit minimal evaluator record + confidence. |
| `normalizer` | Grade scales, A–F↔1–4 crosswalk, evaluator identity resolution, year/level. |
| `store` | Resumable processing store (SQLite); provenance (URL + checksum), no PDF bytes. |
| `refresh` | Watermark + incremental orchestration for the bi-annual re-harvest. |

No code bodies yet — these are responsibility boundaries to validate against the A1 spike.

---

## 8. Open harvesting questions

- **Q1 — OAI set spec.** Confirm a per-collection IES set exists (`col_20.500.11956_1918`?) or
  whether we harvest the FSV community set (`com_20.500.11956_1905`) and filter to IES in the
  mapper. Verify with one live `GetRecord&metadataPrefix=xoai` before building.
- **Q2 — Evaluator identity resolution.** Is there a stable authority ID in `dim`/`xoai`
  (preferred), or must we fuzzy-match names across titles / diacritics / `Surname, First` /
  maiden names? Decides whether identity is a lookup or a matching problem.
- **Q3 — A–F ↔ 1–4 grade mapping.** The proposed-grade crosswalk between the IES English
  rubric and the older FSV Czech scale is **unofficial** — pin down a defensible mapping and
  mark it as an assumption.
- **Q4 — Incremental re-harvest.** Confirm OAI `from`/`until` datestamps are reliable for the
  ~6-month refresh, and define the watermark + re-extraction policy (what triggers a posudek
  re-parse: checksum change? new confidence threshold?).
- **Q5 — Posudek form-type detection.** How to robustly route IES-English vs FSV-Czech forms
  (and detect scanned PDFs needing OCR) before extraction — header sniff, keyword anchors, or
  layout heuristics?
- **Q6 — Legal field-level verdict.** Named vs. anonymised/aggregated evaluators is still open
  (see app-architecture deferred decisions) and may constrain what `store` persists.
