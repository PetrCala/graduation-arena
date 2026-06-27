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
