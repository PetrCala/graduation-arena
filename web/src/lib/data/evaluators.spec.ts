import { describe, it, expect } from 'vitest';
import type { EvaluatorStats } from '$schemas';
import {
	EVALUATOR_STATS_URL,
	findByName,
	loadEvaluatorStats,
	lookupPair,
	normalizeName,
	type FetchLike
} from './evaluators';

const SAMPLE: EvaluatorStats[] = [
	{
		evaluator: { name: 'doc. PhDr. Adam Geršl Ph.D.', id: 'gersl-adam' },
		total_theses: 4,
		grade_distribution: { '1': 2, '2': 1, '3': 1 },
		grade_probabilities: { '1': 0.5, '2': 0.25, '3': 0.25 },
		last_updated: '2026-06-27'
	},
	{
		evaluator: { name: 'PhDr. Jaromír Baxa Ph.D.', id: 'baxa-jaromir' },
		total_theses: 2,
		grade_distribution: { '1': 1, '2': 1 },
		grade_probabilities: { '1': 0.5, '2': 0.5 },
		last_updated: '2026-06-27'
	}
];

/** Build a stub fetch that returns the given payload (or an HTTP error). */
function stubFetch(payload: unknown, ok = true, status = 200): FetchLike {
	return async () => ({
		ok,
		status,
		json: async () => payload
	});
}

describe('normalizeName', () => {
	it('strips titles, diacritics, and ordering differences', () => {
		expect(normalizeName('doc. PhDr. Adam Geršl Ph.D.')).toBe('adam gersl');
		// same identity, no titles, reversed order, no diacritics
		expect(normalizeName('Gersl Adam')).toBe('adam gersl');
	});

	it('returns an empty string for title-only or blank input', () => {
		expect(normalizeName('   ')).toBe('');
		expect(normalizeName('Ph.D.')).toBe('');
	});
});

describe('findByName', () => {
	it('finds an evaluator despite title/diacritic/order differences', () => {
		const hit = findByName(SAMPLE, 'adam gersl');
		expect(hit).not.toBeNull();
		expect(hit?.evaluator.id).toBe('gersl-adam');
	});

	it('returns null when no evaluator matches', () => {
		expect(findByName(SAMPLE, 'Někdo Neznámý')).toBeNull();
	});

	it('returns null for empty input', () => {
		expect(findByName(SAMPLE, '')).toBeNull();
	});
});

describe('lookupPair', () => {
	it('resolves both supervisor and opponent when present', () => {
		const result = lookupPair(SAMPLE, 'doc. PhDr. Adam Geršl Ph.D.', 'Jaromír Baxa');
		expect(result.supervisor?.evaluator.id).toBe('gersl-adam');
		expect(result.opponent?.evaluator.id).toBe('baxa-jaromir');
	});

	it('resolves each side independently (partial match)', () => {
		const result = lookupPair(SAMPLE, 'Adam Geršl', 'Unknown Person');
		expect(result.supervisor?.evaluator.id).toBe('gersl-adam');
		expect(result.opponent).toBeNull();
	});

	it('returns both null when neither name matches', () => {
		const result = lookupPair(SAMPLE, 'Nobody One', 'Nobody Two');
		expect(result.supervisor).toBeNull();
		expect(result.opponent).toBeNull();
	});
});

describe('distribution / probability shape', () => {
	it('exposes counts that sum to total_theses and probabilities that sum to ~1', () => {
		for (const stats of SAMPLE) {
			const counts = Object.values(stats.grade_distribution ?? {});
			const countSum = counts.reduce((a, b) => a + b, 0);
			expect(countSum).toBe(stats.total_theses);

			const probs = Object.values(stats.grade_probabilities ?? {});
			const probSum = probs.reduce((a, b) => a + b, 0);
			expect(probSum).toBeCloseTo(1, 5);
			// every grade with a count has a probability and vice versa
			expect(Object.keys(stats.grade_probabilities ?? {}).sort()).toEqual(
				Object.keys(stats.grade_distribution ?? {}).sort()
			);
		}
	});
});

describe('loadEvaluatorStats', () => {
	it('loads and returns the stats array', async () => {
		const stats = await loadEvaluatorStats(stubFetch(SAMPLE));
		expect(stats).toHaveLength(2);
		expect(stats[0].evaluator.name).toContain('Geršl');
	});

	it('defaults to the static aggregates URL', async () => {
		let requested = '';
		const fetchFn: FetchLike = async (url) => {
			requested = url;
			return { ok: true, status: 200, json: async () => SAMPLE };
		};
		await loadEvaluatorStats(fetchFn);
		expect(requested).toBe(EVALUATOR_STATS_URL);
	});

	it('throws on a non-ok response', async () => {
		await expect(loadEvaluatorStats(stubFetch(null, false, 404))).rejects.toThrow(/HTTP 404/);
	});

	it('throws when the payload is not an array', async () => {
		await expect(loadEvaluatorStats(stubFetch({ not: 'an array' }))).rejects.toThrow(/array/);
	});
});
