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
 * Initials for an evaluator, used as the avatar fallback when no photo is available.
 *
 * Drops academic titles the same way {@link normalizeName} does (so
 * "doc. PhDr. Adam Geršl Ph.D." → "AG"), then takes the first letter of the first and last
 * remaining name tokens, upper-cased. Diacritics are preserved on the kept letters. Falls
 * back to the first character of the raw input, or "?" when there is nothing usable.
 */
export function evaluatorInitials(name: string): string {
	// Drop dots first so "Ph.D." / "M.A." collapse to single tokens the title filter
	// recognises, while keeping case and diacritics on the letters we actually display.
	const tokens = name
		.replace(/\./g, '')
		.split(/[^\p{L}\p{N}]+/u)
		.filter((token) => token.length > 0);
	const fold = (token: string) => token.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
	const names = tokens.filter((token) => !TITLE_TOKENS.has(fold(token)));
	if (names.length === 0) {
		const first = name.trim()[0];
		return first ? first.toUpperCase() : '?';
	}
	const first = names[0][0];
	const last = names.length > 1 ? names[names.length - 1][0] : '';
	return (first + last).toUpperCase();
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

// ---------------------------------------------------------------------------
// Supervisor explorer (#42): gating, ranking metrics, sorting, and search over
// the full evaluator directory. The page lets a student browse and rank every
// served evaluator to choose a supervisor; sorting a column *is* the leaderboard.
// ---------------------------------------------------------------------------

/** Grade string for the top (best) grade on the 1–4 scale. */
const TOP_GRADE = '1';

/**
 * Provisional minimum thesis count for an evaluator to be served.
 *
 * GDPR served-boundary safeguard (issue #18): a per-named-evaluator grade profile is
 * personal data and must be suppressed below a minimum group size. The exact threshold
 * and opt-out policy are still being settled in #18; until the served projection lands,
 * the web app gates client-side with this conservative default — change it here, in one
 * place, when #18 fixes the policy.
 */
export const MIN_THESES_GATE = 5;

/** Whether an evaluator clears the min-N served boundary (see {@link MIN_THESES_GATE}). */
export function meetsMinN(stats: EvaluatorStats, threshold: number = MIN_THESES_GATE): boolean {
	return stats.total_theses >= threshold;
}

/** Keep only evaluators that pass min-N gating, preserving input order. */
export function gateEvaluators(
	stats: readonly EvaluatorStats[],
	threshold: number = MIN_THESES_GATE
): EvaluatorStats[] {
	return stats.filter((s) => meetsMinN(s, threshold));
}

/**
 * Probability the evaluator awards the top grade ("1") — the "generosity" metric.
 * Falls back to the {@link gradeBreakdown} value (count / total) and is `0` when no
 * grade-1 information is recorded.
 */
export function probabilityOfTopGrade(stats: EvaluatorStats): number {
	const top = gradeBreakdown(stats).find((row) => row.grade === TOP_GRADE);
	return top?.probability ?? 0;
}

/**
 * Mean awarded grade — Σ grade × probability, renormalised by the probability mass so
 * rounding in the source (probabilities that sum to ~0.999) does not skew it.
 *
 * On the 1–4 scale (1 = best) a *higher* mean means a *stricter* grader, so this doubles
 * as the strictness metric. Returns `null` when no grades are recorded.
 */
export function meanGrade(stats: EvaluatorStats): number | null {
	const rows = gradeBreakdown(stats);
	const mass = rows.reduce((sum, row) => sum + row.probability, 0);
	if (mass <= 0) return null;
	const weighted = rows.reduce((sum, row) => sum + Number(row.grade) * row.probability, 0);
	return weighted / mass;
}

/** Total theses an evaluator supervised vs. opposed. Missing buckets count as 0. */
export interface RoleSplit {
	supervisor: number;
	opponent: number;
}

/** Total theses an evaluator graded at bachelor vs. master level. Missing buckets count as 0. */
export interface LevelSplit {
	bachelor: number;
	master: number;
}

/** Sum every grade count in a `grade → count` bucket; `0` for a missing/empty bucket. */
function sumGradeCounts(bucket: Record<string, number> | null | undefined): number {
	if (!bucket) return 0;
	return Object.values(bucket).reduce((sum, n) => sum + n, 0);
}

/** Supervisor-vs-opponent thesis totals from {@link EvaluatorStats.by_role}. */
export function roleSplit(stats: EvaluatorStats): RoleSplit {
	return {
		supervisor: sumGradeCounts(stats.by_role?.supervisor),
		opponent: sumGradeCounts(stats.by_role?.opponent)
	};
}

/** Bachelor-vs-master thesis totals from {@link EvaluatorStats.by_level}. */
export function levelSplit(stats: EvaluatorStats): LevelSplit {
	return {
		bachelor: sumGradeCounts(stats.by_level?.bachelor),
		master: sumGradeCounts(stats.by_level?.master)
	};
}

/** Columns the explorer table can sort by. Sorting one *is* the leaderboard. */
export type EvaluatorSortKey = 'name' | 'total_theses' | 'p_top_grade' | 'strictness';

/** Sort direction. `desc` puts the largest value (or strictest/most generous) first. */
export type SortDirection = 'asc' | 'desc';

/** The numeric value a metric key ranks on; `null` when the metric is undefined. */
function metricValue(stats: EvaluatorStats, key: Exclude<EvaluatorSortKey, 'name'>): number | null {
	switch (key) {
		case 'total_theses':
			return stats.total_theses;
		case 'p_top_grade':
			return probabilityOfTopGrade(stats);
		case 'strictness':
			return meanGrade(stats);
	}
}

/**
 * Deterministic, direction-independent tie-break so equal rows keep a stable order:
 * by display name, then by `id` slug (#17).
 */
function tieBreak(a: EvaluatorStats, b: EvaluatorStats): number {
	const byName = a.evaluator.name.localeCompare(b.evaluator.name);
	if (byName !== 0) return byName;
	return (a.evaluator.id ?? '').localeCompare(b.evaluator.id ?? '');
}

/**
 * Sort evaluators by a column, returning a new array (input is not mutated).
 *
 * Evaluators whose metric is `null` (no grades) always sort last, regardless of
 * direction, so an unknown value never masquerades as the most generous or strictest.
 * Ties fall back to {@link tieBreak} for a stable, reproducible order.
 */
export function sortEvaluators(
	stats: readonly EvaluatorStats[],
	key: EvaluatorSortKey,
	direction: SortDirection = 'desc'
): EvaluatorStats[] {
	const dir = direction === 'asc' ? 1 : -1;
	return [...stats].sort((a, b) => {
		if (key === 'name') {
			const byName = normalizeName(a.evaluator.name).localeCompare(normalizeName(b.evaluator.name));
			return byName !== 0 ? dir * byName : tieBreak(a, b);
		}
		const av = metricValue(a, key);
		const bv = metricValue(b, key);
		if (av === null || bv === null) {
			if (av === null && bv === null) return tieBreak(a, b);
			return av === null ? 1 : -1; // nulls last in both directions
		}
		return av !== bv ? dir * (av - bv) : tieBreak(a, b);
	});
}

/**
 * Fuzzy-filter evaluators by a free-text query, reusing the tolerant {@link normalizeName}
 * folding (drops academic titles and diacritics, ignores name order). The query matches
 * when every folded query token is a substring of the folded evaluator name, so "gersl",
 * "adam g", and "Geršl Adam" all match "doc. PhDr. Adam Geršl Ph.D.". An empty or
 * title-only query returns the list unchanged.
 */
export function filterEvaluators(
	stats: readonly EvaluatorStats[],
	query: string
): EvaluatorStats[] {
	const folded = normalizeName(query);
	if (folded.length === 0) return [...stats];
	const tokens = folded.split(' ');
	return stats.filter((s) => {
		const name = normalizeName(s.evaluator.name);
		return tokens.every((token) => name.includes(token));
	});
}
