<script lang="ts">
	import { lookupPair, type EvaluatorPairLookup } from '$lib/data/evaluators';
	import type { EvaluatorStats } from '$schemas';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const stats = $derived<EvaluatorStats[]>(data.stats);

	let supervisorName = $state('');
	let opponentName = $state('');

	const result = $derived<EvaluatorPairLookup | null>(
		supervisorName || opponentName ? lookupPair(stats, supervisorName, opponentName) : null
	);

	function topGrade(s: EvaluatorStats): string {
		const probs = s.grade_probabilities ?? {};
		const entries = Object.entries(probs);
		if (entries.length === 0) return '—';
		const [grade, p] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
		return `${grade} (${Math.round(p * 100)}%)`;
	}
</script>

<svelte:head>
	<title>Graduation Arena — evaluator grade statistics</title>
</svelte:head>

<main class="mx-auto max-w-2xl p-6">
	<h1 class="text-2xl font-bold">Graduation Arena</h1>
	<p class="mt-1 text-gray-600">
		Look up per-evaluator grade statistics by supervisor and opponent. Runs entirely in your browser
		against precomputed aggregates.
	</p>

	<form class="mt-6 grid gap-4 sm:grid-cols-2">
		<label class="flex flex-col gap-1">
			<span class="text-sm font-medium">Supervisor</span>
			<input
				class="rounded border border-gray-300 px-3 py-2"
				placeholder="e.g. Adam Geršl"
				bind:value={supervisorName}
			/>
		</label>
		<label class="flex flex-col gap-1">
			<span class="text-sm font-medium">Opponent</span>
			<input
				class="rounded border border-gray-300 px-3 py-2"
				placeholder="e.g. Jaromír Baxa"
				bind:value={opponentName}
			/>
		</label>
	</form>

	{#if result}
		<section class="mt-6 grid gap-4 sm:grid-cols-2">
			{#each [['Supervisor', result.supervisor], ['Opponent', result.opponent]] as const as [role, hit] (role)}
				<article class="rounded border border-gray-200 p-4">
					<h2 class="text-sm font-semibold tracking-wide text-gray-500 uppercase">{role}</h2>
					{#if hit}
						<p class="mt-1 font-medium">{hit.evaluator.name}</p>
						<p class="text-sm text-gray-600">{hit.total_theses} theses</p>
						<p class="text-sm text-gray-600">Most likely grade: {topGrade(hit)}</p>
					{:else}
						<p class="mt-1 text-sm text-gray-500">No statistics found.</p>
					{/if}
				</article>
			{/each}
		</section>
	{/if}

	<p class="mt-8 text-xs text-gray-400">
		Showing mock data ({stats.length} evaluators). Real aggregates land via the pipeline.
	</p>
</main>
