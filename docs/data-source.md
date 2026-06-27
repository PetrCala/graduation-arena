# Data source reference — IES theses

Durable technical facts for harvesting IES (Institute of Economic Studies, FSV, Charles University) theses. Engineering only.

## Where the data is

- **Public repository: `dspace.cuni.cz`** (DSpace, "Digitální repozitář UK"). Target this — **not** `is.cuni.cz`/SIS (SIS is the upstream workflow system; the public artifacts are mirrored to DSpace).
- IES theses live under the **Faculty of Social Sciences** community; filter to department `Institut ekonomických studií`.
- Everything below is public **without login**.

## Per-thesis fields available

Each item page exposes (structured): title (cs/en), author, **thesis advisor (vedoucí)**, **opponent**, consultant, department/institute, defense date, **defense grade** (`Výborně` / `Velmi dobře` / `Dobře` / `Neprospěl`), language.

Attached public PDFs: thesis text, abstracts, `Posudek vedoucího`, `Posudek oponenta`, `Záznam o průběhu obhajoby` (defense record).

→ The core dataset (advisor, opponent, grade) is **structured** — no PDF mining needed for the happy path. Fallback for missing grade: parse `Záznam o průběhu obhajoby`. Do not parse review text.

## Access routes

- **OAI-PMH (preferred for bulk):** `https://dspace.cuni.cz/oai/request`
  - FSV set: `setSpec=com_20.500.11956_1905`
  - **Format matters:** `oai_dc` **omits the grade** and collapses advisor/opponent/consultant into undifferentiated `dc:contributor`. Use **`xoai`** or **`dim`** for full metadata (grade + role-tagged names). *Verify with one `GetRecord&metadataPrefix=xoai` before building.*
  - Item id form: `oai:dspace.cuni.cz:20.500.11956/<id>`
- **Item page:** `https://dspace.cuni.cz/handle/20.500.11956/<id>` ; bitstreams under `/bitstream/handle/...`
- **Sitemaps:** `https://dspace.cuni.cz/sitemap`, `/htmlmap`
- Example IES item for testing: `handle/20.500.11956/176640`

## Access constraints (robots.txt)

- **Disallowed for everyone:** `/discover`, `/search-filter`, `/browse` → cannot enumerate via the browse/search UI. **Enumerate via OAI-PMH or sitemap instead.**
- Item pages (`/handle/...`) and bitstreams are **allowed**.
- Named crawlers rate-limited to **1 request / 30s** (`crawl-delay: 30`). Honour this for any HTML/PDF fetching; OAI bulk harvest sidesteps it. Send a real User-Agent with contact info.

## Scale

Order of a few thousand IES bachelor+master theses, growing ~hundreds/year. Small by scraping standards. Exact count via OAI FSV set filtered to IES.
