<script lang="ts">
	import { resolve } from '$app/paths';
	import { lookupPair, type EvaluatorPairLookup } from '$lib/data/evaluators';
	import EvaluatorResult from '$lib/components/EvaluatorResult.svelte';
	import type { EvaluatorStats } from '$schemas';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const stats = $derived<EvaluatorStats[]>(data.stats);

	let supervisorName = $state('');
	let opponentName = $state('');

	const hasQuery = $derived(supervisorName.trim().length > 0 || opponentName.trim().length > 0);

	const result = $derived<EvaluatorPairLookup | null>(
		hasQuery ? lookupPair(stats, supervisorName, opponentName) : null
	);
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
	<p class="mt-2 text-sm">
		<a class="text-gray-500 underline hover:text-gray-900" href={resolve('/evaluators')}>
			Browse all evaluators → choose your supervisor
		</a>
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
			<EvaluatorResult role="Supervisor" name={supervisorName} stats={result.supervisor} />
			<EvaluatorResult role="Opponent" name={opponentName} stats={result.opponent} />
		</section>
	{/if}

	<p class="mt-8 text-xs text-gray-400">
		Showing mock data ({stats.length} evaluators). Real aggregates land via the pipeline.
	</p>
</main>
