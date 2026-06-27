# Pipeline build — handoff (@mikulenka2001)

You own the **pipeline track** — the Python harvester that pulls IES thesis data from
`dspace.cuni.cz`. The design is merged; the job now is to build the real scraper. You'll do
it through **Claude Code**, one GitHub issue at a time.

Tracked issues (all assigned to you):

| Step | Issue | What it does |
| --- | --- | --- |
| 1 | [#9](https://github.com/PetrCala/graduation-arena/issues/9) (K1) | **Done — merged.** CLI skeleton with `scrape/parse/aggregate/build` stubs. |
| 2 | [#22](https://github.com/PetrCala/graduation-arena/issues/22) (A1) | Spike: confirm the source exposes the fields; save real fixtures. |
| 3 | [#23](https://github.com/PetrCala/graduation-arena/issues/23) (A2) | Implement `scrape` — pull records via OAI-PMH. |
| 4 | [#24](https://github.com/PetrCala/graduation-arena/issues/24) (A3) | Implement `parse` — raw records into typed records. |
| 5 | [#25](https://github.com/PetrCala/graduation-arena/issues/25) (A4) | Implement `aggregate` + `build` — the per-evaluator JSON the site reads. |

Do steps 2→5 **in order** — each depends on the previous one.

> **⚠ Legal gate ([#14](https://github.com/PetrCala/graduation-arena/issues/14)).**
> Production scraping and committing real records are gated by the named-vs-anonymised
> go/no-go decision. You **can** run the read-only `xoai` verification in A1 (#22) now, but
> **hold on committing real fixtures and on any live `scrape` run until #14 is decided.**
> Check with Petr before that step.

## 0. One-time setup (~15 min)

```bash
git clone https://github.com/PetrCala/graduation-arena.git
cd graduation-arena

gh auth login          # GitHub CLI, logged in
# install uv: https://docs.astral.sh/uv/getting-started/installation/

claude                 # start Claude Code in the repo
```

On start, Claude Code reads `CLAUDE.md` (our workflow rules) and has a built-in
**`dspace-harvest`** skill — the playbook for this exact scraper. Nothing to install; just
mention it in prompts and it uses it.

Sanity-check that K1 is in place:

```bash
cd pipeline && uv run ga-pipeline --help     # should list scrape/parse/aggregate/build
```

## 1. How we work here (read once)

- **Every task is a GitHub Issue.** Branch per issue named `issue-<n>-<slug>`, small focused
  PRs, put `Closes #<n>` in the PR body, merge into `master`.
- **Commits:** imperative mood ("Add scraper", not "Added"), every line under 100 chars, and
  **no AI/Claude attribution lines.** Claude Code already knows this from `CLAUDE.md`.
- **Let Claude drive, but review every diff before it commits.** It proposes a branch, code,
  and a PR — you approve each step.

## 2. Step-by-step

### Step 2 — A1 spike (#22): prove the source has what we need

Read-only. Confirms the live repository returns the grade and the supervisor/opponent names
in the `xoai` format before any scraper code is written.

> **Paste into Claude Code:**
> "Use the `dspace-harvest` skill. Run a single OAI-PMH `GetRecord` with
> `metadataPrefix=xoai` against the example IES record `handle/20.500.11956/206686` on
> `dspace.cuni.cz`. Confirm the response contains the **final defense grade** and
> **role-tagged supervisor and opponent** names. Then save ~10–15 real records as fixtures
> in `data/fixtures/`, and write what you found (the actual field paths, the grade format)
> into `docs/`. Follow the politeness rules in the skill. This is issue #22 — open a PR with
> `Closes #22`."

**Done when:** fixtures are committed and the note says exactly which field holds the grade
and the two names. **If a field is missing, stop and tell Petr** — it changes the plan.

### Step 3 — A2 (#23): implement `scrape`

> **Paste into Claude Code:**
> "Use the `dspace-harvest` skill and the fixtures from #22. Implement the `scrape`
> subcommand in `pipeline/src/ga_pipeline/cli.py`: enumerate IES theses via OAI-PMH
> `ListRecords` (`xoai` format, follow resumption tokens), map each into a `RawThesis`
> (validate with the pydantic model in `schemas/`), and save to a local SQLite/Parquet
> store. Add `--from`/`--until` for incremental runs. Respect the User-Agent + rate-limit
> rules in the skill. Write tests against the fixtures (no live network in CI). This is
> issue #23 — open a PR with `Closes #23`."

**Done when:** `ga-pipeline scrape` populates a local store from the fixtures in tests, and a
real run fetches IES records within the rate limits.

### Steps 4 & 5 — A3 (#24) and A4 (#25)

Same pattern, shorter prompts:

> **A3 (#24):** "Implement the `parse` subcommand: turn the stored `RawThesis` records into
> `ParsedThesis` (title, author, year, level, supervisor, opponent, normalized grade) using
> the field map from #22. Handle missing-grade and not-yet-defended records. Test against the
> fixtures. PR with `Closes #24`."

> **A4 (#25):** "Implement `aggregate` + `build`: group parsed theses by evaluator into
> `EvaluatorStats` and write `data/aggregates/*.json`. Apply the min-N gating from issue #18.
> Test that probabilities sum to ~1. PR with `Closes #25`."

## 3. If you get stuck

- Ask Claude directly: *"What does the `dspace-harvest` skill say about X?"* or
  *"Show me the `RawThesis` schema."*
- **Don't** crawl `/discover` or `/browse` on the source — it's banned by robots.txt; the
  skill explains why and what to use instead.
- Keep PRs small (one subcommand each). If a PR gets big, ask Claude to split it.
