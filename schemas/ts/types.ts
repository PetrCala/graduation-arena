// v0 — to be auto-generated from schemas/json once web tooling (K1) lands.
//
// These TypeScript types mirror the pydantic models in schemas/models.py (the single
// source of truth) and the JSON Schema in schemas/json/. They are hand-authored for v0:
// running `npx json-schema-to-typescript` over the per-model schemas works, but emits
// noisy, name-clashing output (duplicate `Evaluator` / `Evaluator1`, a per-scalar alias
// for every field). Until K1 wires up a clean generation step in the web toolchain, this
// faithful hand-authored mirror is the contract the web app consumes.
//
// Keep in sync with schemas/models.py. Anything marked TODO there is loose here too.

/** Thesis level. */
export type Level = "bachelor" | "master";

/** Role an evaluator plays for a given thesis. */
export type EvaluatorRole = "supervisor" | "opponent";

/**
 * Defense grade on the provisional 1-4 scale (1 = best).
 *
 * TODO(v0): exact IES scale unconfirmed (see GRADE SCALE NOTE in models.py). Kept as a
 * bare number so the scale can change without reshaping the contract.
 */
export type Grade = number;

/** A person who evaluates a thesis (supervisor or opponent). */
export interface Evaluator {
  name: string;
  /** Stable identifier, if known. Scheme TBD (TODO v0). */
  id?: string | null;
  /** Role for the referencing thesis, if applicable. */
  role?: EvaluatorRole | null;
}

/**
 * A raw scraped thesis record, before parsing/normalisation.
 *
 * v0 — intentionally minimal; everything beyond provenance lives untyped in `raw_fields`.
 */
export interface RawThesis {
  source_id: string;
  source_url: string;
  /** UTC timestamp (ISO 8601 string) when the record was fetched. */
  fetched_at: string;
  /** Free-form bag of raw scraped fields. Untyped for v0. */
  raw_fields?: Record<string, unknown>;
}

/** A normalised thesis record produced by the parser. */
export interface ParsedThesis {
  id: string;
  title: string;
  author: string;
  year: number;
  level: Level;
  /** Language code, e.g. "cs" / "en" (TODO v0: representation unconfirmed). */
  language?: string | null;
  supervisor: Evaluator;
  opponent: Evaluator;
  /** Overall defense grade (TODO v0: scale unconfirmed). */
  defense_grade?: Grade | null;
  abstract?: string | null;
  source_url: string;
}

/**
 * Per-evaluator aggregated grade statistics — the artifact the web app serves.
 *
 * Distributions/probabilities are keyed by the string form of the grade so the JSON is
 * self-describing and the grade type can change without reshaping the contract.
 */
export interface EvaluatorStats {
  evaluator: Evaluator;
  total_theses: number;
  /** Count of theses per grade, keyed by grade as a string. */
  grade_distribution?: Record<string, number>;
  /** Probability of each grade (counts normalised to ~1.0). */
  grade_probabilities?: Record<string, number>;
  /** Optional grade distribution broken down by evaluator role. */
  by_role?: Record<string, Record<string, number>> | null;
  /** Optional grade distribution broken down by thesis level. */
  by_level?: Record<string, Record<string, number>> | null;
  /** Date (ISO 8601 string, YYYY-MM-DD) these aggregates were last recomputed. */
  last_updated: string;
}
