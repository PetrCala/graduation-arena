# schemas

The shared **data contract** between the pipeline (producer) and the web app (consumer).

Single-sourced in **pydantic**. JSON Schema and the TypeScript types used by the web app are
*generated* from it — never hand-written — so the two sides cannot drift.

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
  models.py          # pydantic v2 — the single source of truth (RawThesis, ParsedThesis,
                     #   Evaluator, EvaluatorStats). Marked v0 / draft; uncertain fields TODO-d.
  export.py          # regenerates schemas/json/ and validates data/fixtures/ against the models
  json/              # generated JSON Schema (do not hand-edit)
  ts/                # TypeScript types for the web app (types.ts + index.ts barrel)
  pyproject.toml     # minimal self-contained deps (pydantic>=2) so export runs without K1
data/fixtures/       # example ParsedThesis + EvaluatorStats JSON, validated by export.py
```

## Regenerate

```bash
python -m venv .venv
.venv/Scripts/python -m pip install "pydantic>=2"   # POSIX: .venv/bin/python
python schemas/export.py                            # writes schemas/json/, validates fixtures
```

`export.py` exits non-zero if any fixture fails to validate, so it doubles as a check.

The TS types in `schemas/ts/` are hand-authored for `v0` (the JSON-Schema generator emits
noisy, name-clashing output). They will be auto-generated from `schemas/json/` once the web
toolchain (K1) lands. Keep them in sync with `models.py` until then.

> **`v0` is a draft.** The exact IES grade scale and any per-criterion sub-scores are
> unconfirmed (see the GRADE SCALE NOTE in `models.py`), and the named-vs-anonymised
> evaluator decision is pending. Unconfirmed fields are marked `TODO(v0)` in `models.py`.
