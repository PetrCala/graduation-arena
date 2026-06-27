import { describe, it, expect } from 'vitest';
import type { EvaluatorStats } from '$schemas';
import {
	EVALUATOR_STATS_URL,
	MIN_THESES_GATE,
	evaluatorInitials,
	filterEvaluators,
	findByName,
	gateEvaluators,
	gradeBreakdown,
	levelSplit,
	loadEvaluatorStats,
	lookupPair,
	meanGrade,
	meetsMinN,
	mostLikelyGrade,
	normalizeName,
	probabilityOfTopGrade,
	roleSplit,
	sortEvaluators,
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

describe('evaluatorInitials', () => {
	it('drops titles and uses the first and last name initials', () => {
		expect(evaluatorInitials('doc. PhDr. Adam Geršl Ph.D.')).toBe('AG');
		expect(evaluatorInitials('prof. Ing. Michal Mejstřík CSc.')).toBe('MM');
		// "M.A." must be treated as a title, not a name token
		expect(evaluatorInitials('Mgr. Barbara Pertold-Gebicka M.A. Ph.D.')).toBe('BG');
	});

	it('returns a single initial for a one-token name', () => {
		expect(evaluatorInitials('Madonna')).toBe('M');
	});

	it('falls back gracefully when there is nothing usable', () => {
		expect(evaluatorInitials('   ')).toBe('?');
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

describe('gradeBreakdown', () => {
	it('returns every grade sorted ascending with count and probability', () => {
		const rows = gradeBreakdown(SAMPLE[0]);
		expect(rows.map((r) => r.grade)).toEqual(['1', '2', '3']);
		expect(rows[0]).toEqual({ grade: '1', count: 2, probability: 0.5 });
	});

	it('includes grades present in only one of the maps and defaults count to 0', () => {
		const rows = gradeBreakdown({
			evaluator: { name: 'Solo Grade' },
			total_theses: 1,
			grade_distribution: { '1': 1 },
			grade_probabilities: { '1': 0.8, '4': 0.2 },
			last_updated: '2026-06-27'
		});
		expect(rows.map((r) => r.grade)).toEqual(['1', '4']);
		expect(rows.find((r) => r.grade === '4')).toEqual({ grade: '4', count: 0, probability: 0.2 });
	});

	it('falls back to count / total_theses when a probability is missing', () => {
		const rows = gradeBreakdown({
			evaluator: { name: 'No Probs' },
			total_theses: 4,
			grade_distribution: { '1': 3, '2': 1 },
			last_updated: '2026-06-27'
		});
		expect(rows.find((r) => r.grade === '1')?.probability).toBeCloseTo(0.75, 5);
	});

	it('returns an empty array when no grades are recorded', () => {
		expect(
			gradeBreakdown({ evaluator: { name: 'Empty' }, total_theses: 0, last_updated: '2026-06-27' })
		).toEqual([]);
	});
});

describe('mostLikelyGrade', () => {
	it('returns the highest-probability grade', () => {
		expect(mostLikelyGrade(SAMPLE[0])?.grade).toBe('1');
	});

	it('returns null when no grades are recorded', () => {
		expect(
			mostLikelyGrade({ evaluator: { name: 'Empty' }, total_theses: 0, last_updated: '2026-06-27' })
		).toBeNull();
	});
});

// --- Supervisor explorer (#42) ---------------------------------------------

/** A small directory: a strict grader, a generous grader, and a below-gate evaluator. */
const DIRECTORY: EvaluatorStats[] = [
	{
		evaluator: { name: 'doc. Strict Grader Ph.D.', id: 'grader-strict' },
		total_theses: 10,
		grade_distribution: { '1': 1, '2': 3, '3': 4, '4': 2 },
		grade_probabilities: { '1': 0.1, '2': 0.3, '3': 0.4, '4': 0.2 },
		by_role: { supervisor: { '1': 1, '2': 1 }, opponent: { '3': 4, '4': 2, '2': 2 } },
		by_level: { bachelor: { '2': 3, '3': 1 }, master: { '1': 1, '3': 3, '4': 2 } },
		last_updated: '2026-06-27'
	},
	{
		evaluator: { name: 'Mgr. Generous Grader', id: 'grader-generous' },
		total_theses: 20,
		grade_distribution: { '1': 16, '2': 4 },
		grade_probabilities: { '1': 0.8, '2': 0.2 },
		by_role: { supervisor: { '1': 12, '2': 3 }, opponent: { '1': 4, '2': 1 } },
		by_level: { bachelor: { '1': 9, '2': 1 }, master: { '1': 7, '2': 3 } },
		last_updated: '2026-06-27'
	},
	{
		evaluator: { name: 'Below Gate', id: 'below-gate' },
		total_theses: 3,
		grade_distribution: { '1': 2, '2': 1 },
		grade_probabilities: { '1': 0.6667, '2': 0.3333 },
		last_updated: '2026-06-27'
	}
];

describe('meetsMinN / gateEvaluators', () => {
	it('admits evaluators at or above the threshold and rejects those below', () => {
		expect(meetsMinN(DIRECTORY[1])).toBe(true); // 20 theses
		expect(meetsMinN(DIRECTORY[2])).toBe(false); // 3 theses, below default gate
		expect(meetsMinN({ ...DIRECTORY[2], total_theses: MIN_THESES_GATE })).toBe(true);
	});

	it('drops below-gate evaluators and preserves input order', () => {
		const gated = gateEvaluators(DIRECTORY);
		expect(gated.map((s) => s.evaluator.id)).toEqual(['grader-strict', 'grader-generous']);
	});

	it('honours a custom threshold', () => {
		expect(gateEvaluators(DIRECTORY, 15).map((s) => s.evaluator.id)).toEqual(['grader-generous']);
	});
});

describe('probabilityOfTopGrade', () => {
	it('reads P(grade 1), falling back to count / total when probabilities are absent', () => {
		expect(probabilityOfTopGrade(DIRECTORY[1])).toBeCloseTo(0.8, 5);
		const noProbs: EvaluatorStats = {
			evaluator: { name: 'No Probs', id: 'no-probs' },
			total_theses: 4,
			grade_distribution: { '1': 3, '2': 1 },
			last_updated: '2026-06-27'
		};
		expect(probabilityOfTopGrade(noProbs)).toBeCloseTo(0.75, 5);
	});

	it('is 0 when no grade-1 information is recorded', () => {
		const noTop: EvaluatorStats = {
			evaluator: { name: 'No Top', id: 'no-top' },
			total_theses: 2,
			grade_distribution: { '2': 2 },
			grade_probabilities: { '2': 1 },
			last_updated: '2026-06-27'
		};
		expect(probabilityOfTopGrade(noTop)).toBe(0);
	});
});

describe('meanGrade (strictness)', () => {
	it('is higher for a stricter grader', () => {
		const strict = meanGrade(DIRECTORY[0]);
		const generous = meanGrade(DIRECTORY[1]);
		expect(strict).not.toBeNull();
		expect(generous).not.toBeNull();
		expect(strict!).toBeGreaterThan(generous!);
	});

	it('renormalises by probability mass so rounded probabilities do not skew it', () => {
		// 0.1+0.3+0.4+0.2 = 1.0 here, so the mean is the exact weighted average.
		expect(meanGrade(DIRECTORY[0])!).toBeCloseTo(2.7, 5);
	});

	it('returns null when no grades are recorded', () => {
		expect(
			meanGrade({ evaluator: { name: 'Empty', id: 'empty' }, total_theses: 0, last_updated: 'x' })
		).toBeNull();
	});
});

describe('roleSplit / levelSplit', () => {
	it('sums the supervisor and opponent buckets', () => {
		expect(roleSplit(DIRECTORY[1])).toEqual({ supervisor: 15, opponent: 5 });
	});

	it('sums the bachelor and master buckets', () => {
		expect(levelSplit(DIRECTORY[1])).toEqual({ bachelor: 10, master: 10 });
	});

	it('treats missing by_role / by_level as zero', () => {
		expect(roleSplit(DIRECTORY[2])).toEqual({ supervisor: 0, opponent: 0 });
		expect(levelSplit(DIRECTORY[2])).toEqual({ bachelor: 0, master: 0 });
	});
});

describe('sortEvaluators', () => {
	it('ranks by total_theses descending by default', () => {
		const order = sortEvaluators(DIRECTORY, 'total_theses').map((s) => s.evaluator.id);
		expect(order).toEqual(['grader-generous', 'grader-strict', 'below-gate']);
	});

	it('ranks by total_theses ascending when asked', () => {
		const order = sortEvaluators(DIRECTORY, 'total_theses', 'asc').map((s) => s.evaluator.id);
		expect(order).toEqual(['below-gate', 'grader-strict', 'grader-generous']);
	});

	it('ranks the most generous grader first by P(1) descending', () => {
		const order = sortEvaluators(DIRECTORY, 'p_top_grade', 'desc').map((s) => s.evaluator.id);
		expect(order[0]).toBe('grader-generous');
	});

	it('ranks the strictest grader first by strictness descending', () => {
		const order = sortEvaluators(DIRECTORY, 'strictness', 'desc').map((s) => s.evaluator.id);
		expect(order[0]).toBe('grader-strict');
	});

	it('sorts by folded name, ignoring titles and diacritics', () => {
		const order = sortEvaluators(DIRECTORY, 'name', 'asc').map((s) => s.evaluator.id);
		expect(order).toEqual(['below-gate', 'grader-generous', 'grader-strict']);
	});

	it('sorts evaluators with no metric last regardless of direction', () => {
		const noGrades: EvaluatorStats = {
			evaluator: { name: 'No Grades', id: 'no-grades' },
			total_theses: 9,
			last_updated: '2026-06-27'
		};
		const pool = [noGrades, ...DIRECTORY];
		expect(sortEvaluators(pool, 'strictness', 'desc').at(-1)?.evaluator.id).toBe('no-grades');
		expect(sortEvaluators(pool, 'strictness', 'asc').at(-1)?.evaluator.id).toBe('no-grades');
	});

	it('does not mutate the input array', () => {
		const input = [...DIRECTORY];
		sortEvaluators(input, 'total_theses');
		expect(input.map((s) => s.evaluator.id)).toEqual(DIRECTORY.map((s) => s.evaluator.id));
	});

	it('breaks ties deterministically by name then id', () => {
		const a: EvaluatorStats = {
			evaluator: { name: 'Same Score', id: 'same-a' },
			total_theses: 5,
			grade_distribution: { '1': 5 },
			grade_probabilities: { '1': 1 },
			last_updated: '2026-06-27'
		};
		const b: EvaluatorStats = { ...a, evaluator: { name: 'Same Score', id: 'same-b' } };
		const order = sortEvaluators([b, a], 'total_theses', 'desc').map((s) => s.evaluator.id);
		expect(order).toEqual(['same-a', 'same-b']);
	});
});

describe('filterEvaluators', () => {
	it('returns the full list for an empty or title-only query', () => {
		expect(filterEvaluators(DIRECTORY, '')).toHaveLength(DIRECTORY.length);
		expect(filterEvaluators(DIRECTORY, '  Ph.D.  ')).toHaveLength(DIRECTORY.length);
	});

	it('matches despite titles, diacritics, and name order', () => {
		const sample: EvaluatorStats[] = [
			{
				evaluator: { name: 'doc. PhDr. Adam Geršl Ph.D.', id: 'gersl-adam' },
				total_theses: 10,
				last_updated: '2026-06-27'
			},
			{
				evaluator: { name: 'PhDr. Jaromír Baxa Ph.D.', id: 'baxa-jaromir' },
				total_theses: 10,
				last_updated: '2026-06-27'
			}
		];
		expect(filterEvaluators(sample, 'gersl').map((s) => s.evaluator.id)).toEqual(['gersl-adam']);
		expect(filterEvaluators(sample, 'Geršl Adam').map((s) => s.evaluator.id)).toEqual([
			'gersl-adam'
		]);
		expect(filterEvaluators(sample, 'adam g').map((s) => s.evaluator.id)).toEqual(['gersl-adam']);
	});

	it('requires every query token to match (AND semantics)', () => {
		expect(filterEvaluators(DIRECTORY, 'generous grader').map((s) => s.evaluator.id)).toEqual([
			'grader-generous'
		]);
		expect(filterEvaluators(DIRECTORY, 'generous strict')).toHaveLength(0);
	});

	it('returns an empty list when nothing matches', () => {
		expect(filterEvaluators(DIRECTORY, 'nonexistent')).toHaveLength(0);
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
