<script lang="ts">
	import { resolve } from '$app/paths';
	import type { EvaluatorStats } from '$schemas';
	import {
		filterEvaluators,
		gateEvaluators,
		levelSplit,
		meanGrade,
		probabilityOfTopGrade,
		roleSplit,
		sortEvaluators,
		type EvaluatorSortKey,
		type SortDirection
	} from '$lib/data/evaluators';
	import GradeDistributionBar from '$lib/components/GradeDistributionBar.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Served boundary (#18): below-gate evaluators are never listed, before any search.
	const gated = $derived<EvaluatorStats[]>(gateEvaluators(data.stats));

	let query = $state('');
	let sortKey = $state<EvaluatorSortKey>('total_theses');
	let sortDir = $state<SortDirection>('desc');

	const rows = $derived(sortEvaluators(filterEvaluators(gated, query), sortKey, sortDir));

	type Column = {
		key: EvaluatorSortKey;
		label: string;
		defaultDir: SortDirection;
		align: 'left' | 'right';
		hint: string;
	};

	const COLUMNS: Column[] = [
		{ key: 'name', label: 'Evaluator', defaultDir: 'asc', align: 'left', hint: 'Sort by name' },
		{
			key: 'total_theses',
			label: 'Theses',
			defaultDir: 'desc',
			align: 'right',
			hint: 'Theses graded — a proxy for how many students they take'
		},
		{
			key: 'p_top_grade',
			label: 'P(1)',
			defaultDir: 'desc',
			align: 'right',
			hint: 'Share of theses graded 1 — sort descending for the most generous graders'
		},
		{
			key: 'strictness',
			label: 'Strictness',
			defaultDir: 'desc',
			align: 'right',
			hint: 'Mean grade on the 1–4 scale; higher = stricter. Sort descending for the toughest'
		}
	];

	function toggleSort(col: Column) {
		if (sortKey === col.key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = col.key;
			sortDir = col.defaultDir;
		}
	}

	function ariaSort(key: EvaluatorSortKey): 'ascending' | 'descending' | 'none' {
		if (sortKey !== key) return 'none';
		return sortDir === 'asc' ? 'ascending' : 'descending';
	}

	const arrow = (key: EvaluatorSortKey) => (sortKey !== key ? '' : sortDir === 'asc' ? '▲' : '▼');
	const pct = (p: number) => `${Math.round(p * 100)}%`;
</script>

<svelte:head>
	<title>Graduation Arena — supervisor explorer</title>
</svelte:head>

{#snippet sortHeader(col: Column)}
	<th scope="col" aria-sort={ariaSort(col.key)} class="px-3 py-2 font-medium">
		<button
			type="button"
			onclick={() => toggleSort(col)}
			title={col.hint}
			class="flex w-full items-center gap-1 hover:text-gray-900 {col.align === 'right'
				? 'justify-end'
				: 'justify-start'} {sortKey === col.key ? 'text-gray-900' : 'text-gray-500'}"
		>
			<span>{col.label}</span>
			<span aria-hidden="true" class="w-3 text-xs text-gray-400">{arrow(col.key)}</span>
		</button>
	</th>
{/snippet}

<main class="mx-auto max-w-5xl p-6">
	<p class="text-sm">
		<a class="text-gray-500 underline hover:text-gray-900" href={resolve('/')}>← Grade lookup</a>
	</p>

	<h1 class="mt-2 text-2xl font-bold">Choose your supervisor</h1>
	<p class="mt-1 text-gray-600">
		Browse every evaluator and rank them by what matters to you. You rarely pick your opponent, but
		you do pick a supervisor — sort a column to find the most generous grader, the toughest, or the
		one who takes the most students. Runs entirely in your browser against precomputed aggregates.
	</p>

	<label class="mt-6 flex flex-col gap-1">
		<span class="text-sm font-medium">Search by name</span>
		<input
			class="max-w-sm rounded border border-gray-300 px-3 py-2"
			placeholder="e.g. Geršl"
			bind:value={query}
		/>
	</label>

	<div class="mt-4 overflow-x-auto">
		<table class="w-full border-collapse text-sm">
			<thead>
				<tr class="border-b border-gray-200 text-left">
					{@render sortHeader(COLUMNS[0])}
					{@render sortHeader(COLUMNS[1])}
					{@render sortHeader(COLUMNS[2])}
					{@render sortHeader(COLUMNS[3])}
					<th scope="col" class="px-3 py-2 font-medium text-gray-500">Grades</th>
					<th scope="col" class="px-3 py-2 text-right font-medium text-gray-500"> Sup. / Opp. </th>
					<th scope="col" class="px-3 py-2 text-right font-medium text-gray-500"> Bc. / Mgr. </th>
				</tr>
			</thead>
			<tbody>
				{#each rows as s (s.evaluator.id ?? s.evaluator.name)}
					{@const role = roleSplit(s)}
					{@const level = levelSplit(s)}
					{@const strict = meanGrade(s)}
					<tr id={s.evaluator.id ?? undefined} class="border-t border-gray-100">
						<td class="px-3 py-2">
							<div class="font-medium text-gray-900">{s.evaluator.name}</div>
							{#if s.evaluator.id}
								<div class="font-mono text-xs text-gray-400">{s.evaluator.id}</div>
							{/if}
						</td>
						<td class="px-3 py-2 text-right tabular-nums">{s.total_theses}</td>
						<td class="px-3 py-2 text-right tabular-nums">{pct(probabilityOfTopGrade(s))}</td>
						<td class="px-3 py-2 text-right tabular-nums">
							{strict !== null ? strict.toFixed(2) : '—'}
						</td>
						<td class="px-3 py-2"><GradeDistributionBar stats={s} /></td>
						<td class="px-3 py-2 text-right text-gray-600 tabular-nums">
							{role.supervisor} / {role.opponent}
						</td>
						<td class="px-3 py-2 text-right text-gray-600 tabular-nums">
							{level.bachelor} / {level.master}
						</td>
					</tr>
				{:else}
					<tr>
						<td colspan="7" class="px-3 py-6 text-center text-sm text-gray-500">
							No evaluators match “{query}”.
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<p class="mt-4 text-xs text-gray-500">
		<span class="font-medium">P(1)</span> is the share of theses graded 1 (best); higher is more
		generous. <span class="font-medium">Strictness</span> is the mean grade on the 1–4 scale, where higher
		means tougher. Sorting a column is the leaderboard.
	</p>

	<p class="mt-2 text-xs text-gray-400">
		Showing {rows.length} of {gated.length} listed evaluators (mock data). Evaluators below the minimum-N
		served boundary are hidden. Real aggregates land via the pipeline.
	</p>
</main>
