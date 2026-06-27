import { loadEvaluatorStats } from '$lib/data/evaluators';
import type { PageLoad } from './$types';

// Fully static: prerender this page at build time. The aggregates are fetched from a
// static asset, so the load runs at build and the data is baked into the page.
export const prerender = true;

export const load: PageLoad = async ({ fetch }) => {
	const stats = await loadEvaluatorStats(fetch);
	return { stats };
};
