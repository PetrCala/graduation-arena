/**
 * Data-access layer for per-evaluator grade statistics.
 *
 * The site is fully static: there is no backend. At runtime the browser fetches the
 * precomputed `EvaluatorStats` aggregates (mock data for now, real pipeline output
 * later) and the supervisor + opponent lookup runs entirely client-side.
 *
 * Types come from the shared data contract in `schemas/ts/` (imported via the
 * `$schemas` alias) so the web app never redefines the contract shape.
 */

import type { EvaluatorStats } from '$schemas';

/** Where the static `EvaluatorStats` aggregates live, relative to the site root. */
export const EVALUATOR_STATS_URL = '/data/evaluator-stats.json';

/**
 * Minimal `fetch` signature this module depends on. Lets callers (and tests) pass
 * SvelteKit's `fetch`, the global `fetch`, or a stub without pulling in DOM types.
 */
export type FetchLike = (input: string) => Promise<{
	ok: boolean;
	status: number;
	json: () => Promise<unknown>;
}>;

/** Result of a combined supervisor + opponent lookup. */
export interface EvaluatorPairLookup {
	supervisor: EvaluatorStats | null;
	opponent: EvaluatorStats | null;
}

/** A single grade's count and probability, ready for display. */
export interface GradeRow {
	/** Grade as it appears in the contract (string form, e.g. "1"). */
	grade: string;
	/** Number of theses that received this grade. */
	count: number;
	/** Probability of this grade (0–1). */
	probability: number;
}

/**
 * Normalise an evaluator name for tolerant matching.
 *
 * Evaluator names carry academic titles ("doc.", "PhDr.", "Ph.D.", "CSc.") and Czech
 * diacritics, and a user typing a name will rarely reproduce them exactly. We compare
 * on a folded form: lower-cased, diacritics stripped, punctuation removed, and common
 * title tokens dropped, so "Gersl Adam" still matches "doc. PhDr. Adam Geršl Ph.D.".
 */
const TITLE_TOKENS = new Set([
	'bc',
	'mgr',
	'ing',
	'phdr',
	'rndr',
	'rsdr',
	'judr',
	'mudr',
	'paeddr',
	'doc',
	'prof',
	'phd',
	'csc',
	'drsc',
	'dr',
	'ma',
	'msc',
	'mba'
]);

export function normalizeName(name: string): string {
	return (
		name
			.normalize('NFD')
			// strip combining diacritical marks (U+0300–U+036F)
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			// drop dots inside abbreviations first, so "Ph.D." / "M.A." collapse to single
			// tokens ("phd" / "ma") that the title filter below recognises
			.replace(/\./g, '')
			// split on anything that is not a latin letter or digit
			.split(/[^a-z0-9]+/)
			.filter((token) => token.length > 0 && !TITLE_TOKENS.has(token))
			.sort()
			.join(' ')
	);
}

/**
 * Load the `EvaluatorStats` aggregates from the static JSON artifact.
 *
 * @param fetchFn fetch implementation (SvelteKit `fetch` in load functions, global
 *   `fetch` in the browser, or a stub in tests).
 * @param url override the source URL (defaults to {@link EVALUATOR_STATS_URL}).
 * @throws if the request fails or the payload is not an array.
 */
export async function loadEvaluatorStats(
	fetchFn: FetchLike,
	url: string = EVALUATOR_STATS_URL
): Promise<EvaluatorStats[]> {
	const res = await fetchFn(url);
	if (!res.ok) {
		throw new Error(`Failed to load evaluator stats from ${url} (HTTP ${res.status})`);
	}
	const data = await res.json();
	if (!Array.isArray(data)) {
		throw new Error(`Evaluator stats at ${url} must be a JSON array`);
	}
	return data as EvaluatorStats[];
}

/**
 * Find a single evaluator's stats by name, using tolerant matching
 * (see {@link normalizeName}). Returns `null` when no evaluator matches.
 */
export function findByName(stats: readonly EvaluatorStats[], name: string): EvaluatorStats | null {
	const target = normalizeName(name);
	if (target.length === 0) return null;
	return stats.find((s) => normalizeName(s.evaluator.name) === target) ?? null;
}

/**
 * Look up the stats for a supervisor + opponent pair by name.
 *
 * Each side resolves independently and is `null` when not found, so a partial match
 * (e.g. a known supervisor with an unknown opponent) still returns useful data
 * instead of failing the whole lookup.
 */
export function lookupPair(
	stats: readonly EvaluatorStats[],
	supervisorName: string,
	opponentName: string
): EvaluatorPairLookup {
	return {
		supervisor: findByName(stats, supervisorName),
		opponent: findByName(stats, opponentName)
	};
}

/**
 * Build the per-grade breakdown for an evaluator, sorted by grade ascending.
 *
 * Grades present in either the distribution or the probabilities are included, so a
 * grade is never silently dropped. Missing counts default to 0 and a missing
 * probability falls back to `count / total_theses` (0 when there are no theses).
 */
export function gradeBreakdown(stats: EvaluatorStats): GradeRow[] {
	const distribution = stats.grade_distribution ?? {};
	const probabilities = stats.grade_probabilities ?? {};
	const grades = new Set([...Object.keys(distribution), ...Object.keys(probabilities)]);
	return [...grades]
		.map((grade) => {
			const count = distribution[grade] ?? 0;
			const probability =
				probabilities[grade] ?? (stats.total_theses > 0 ? count / stats.total_theses : 0);
			return { grade, count, probability };
		})
		.sort((a, b) => Number(a.grade) - Number(b.grade));
}

/**
 * The single most likely grade for an evaluator, or `null` when no grades are recorded.
 * Ties resolve to the lowest (best) grade, since {@link gradeBreakdown} is sorted ascending.
 */
export function mostLikelyGrade(stats: EvaluatorStats): GradeRow | null {
	const rows = gradeBreakdown(stats);
	if (rows.length === 0) return null;
	return rows.reduce((best, row) => (row.probability > best.probability ? row : best));
}
