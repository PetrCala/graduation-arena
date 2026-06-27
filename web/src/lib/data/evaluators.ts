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
