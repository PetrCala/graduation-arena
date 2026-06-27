# schemas

The shared **data contract** between the pipeline (producer) and the web app (consumer).

Single-sourced in **pydantic**. JSON Schema is *generated* from it; the TypeScript types are
hand-authored for `v0` but checked against the schema (see `--check` below), so producer and
consumer cannot silently drift.

Planned types:

- `RawThesis` — as scraped from the source.
- `ParsedThesis` — normalised fields (title, author, year, level, language, supervisor,
  opponent, defense grade, abstract, …).
- `EvaluatorStats` — aggregated per-evaluator grade distributions and probabilities.

A provisional **`v0`** draft is the next task (K2). The fields firm up once real source
fixtures exist (A1) and the legal verdict (named vs. anonymised evaluators) lands, so treat
`v0` as deliberately loose. See [../docs/app-architecture.md](../docs/app-architecture.md).

## Layout (`v0`)

```
schemas/
  ga_schemas/        # the Python package (importable as ga_schemas)
    models.py        # pydantic v2 — the single source of truth (RawThesis, ParsedThesis,
                     #   Evaluator, EvaluatorStats). Marked v0 / draft; uncertain fields TODO-d.
    export.py        # regenerates json/ + validates fixtures; --check verifies no drift
  json/              # generated JSON Schema (do not hand-edit)
  ts/                # TypeScript types for the web app (types.ts + index.ts barrel)
  pyproject.toml     # minimal self-contained deps (pydantic) so export runs without K1
data/fixtures/       # example ParsedThesis + EvaluatorStats JSON, validated by export.py
```

## Regenerate & check

Run from this directory:

```bash
cd schemas
python -m venv .venv
.venv/Scripts/python -m pip install -e .            # POSIX: .venv/bin/python
.venv/Scripts/python -m ga_schemas.export           # writes json/, validates fixtures
.venv/Scripts/python -m ga_schemas.export --check   # verify no drift (what CI runs)
```

`--check` generates nothing; it fails if the committed `json/` is stale, a fixture is invalid,
or `ts/types.ts` disagrees with the schema on field names, optionality, or enum members. CI
(`.github/workflows/schemas.yml`) runs `--check` plus `tsc --strict`.

The TS types in `ts/` are hand-authored for `v0` (the JSON-Schema generator emits noisy,
name-clashing output). The `--check` drift guard keeps them honest until the web toolchain
(K1) wires up clean auto-generation from `json/`.

> **`v0` is a draft.** The exact IES grade scale and any per-criterion sub-scores are
> unconfirmed (see the GRADE SCALE NOTE in `models.py`), and the named-vs-anonymised
> evaluator decision is pending. Unconfirmed fields are marked `TODO(v0)` in `models.py`.
