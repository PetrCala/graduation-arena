<script lang="ts">
	import type { EvaluatorStats } from '$schemas';
	import { gradeBreakdown, mostLikelyGrade } from '$lib/data/evaluators';
	import Avatar from '$lib/components/Avatar.svelte';

	let { role, name, stats }: { role: string; name: string; stats: EvaluatorStats | null } =
		$props();

	const rows = $derived(stats ? gradeBreakdown(stats) : []);
	const topGrade = $derived(stats ? mostLikelyGrade(stats) : null);
	const trimmedName = $derived(name.trim());

	const pct = (p: number) => `${Math.round(p * 100)}%`;
</script>

<article class="rounded border border-gray-200 p-4">
	<h2 class="text-sm font-semibold tracking-wide text-gray-500 uppercase">{role}</h2>

	{#if stats}
		<div class="mt-1 flex items-center gap-3">
			<Avatar name={stats.evaluator.name} src={stats.evaluator.image_url} />
			<div>
				<p class="font-medium">{stats.evaluator.name}</p>
				<p class="text-sm text-gray-600">
					{stats.total_theses} theses{#if topGrade}
						· most likely grade {topGrade.grade} ({pct(topGrade.probability)}){/if}
				</p>
			</div>
		</div>

		{#if rows.length > 0}
			<ul class="mt-3 space-y-2">
				{#each rows as row (row.grade)}
					{@const isTop = topGrade?.grade === row.grade}
					<li>
						<div class="flex items-baseline justify-between text-sm">
							<span class={isTop ? 'font-medium text-gray-900' : 'text-gray-600'}>
								Grade {row.grade}{#if isTop}
									<span class="text-xs font-normal text-gray-400">· most likely</span>{/if}
							</span>
							<span class="text-gray-600 tabular-nums">
								{pct(row.probability)} <span class="text-gray-400">· n={row.count}</span>
							</span>
						</div>
						<div class="mt-1 h-2 overflow-hidden rounded bg-gray-100" aria-hidden="true">
							<div
								class="h-full rounded {isTop ? 'bg-gray-900' : 'bg-gray-400'}"
								style="width: {Math.round(row.probability * 100)}%"
							></div>
						</div>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="mt-3 text-sm text-gray-500">No grade breakdown recorded.</p>
		{/if}

		<p class="mt-3 text-xs text-gray-400">Updated {stats.last_updated}</p>
	{:else if trimmedName}
		<p class="mt-1 text-sm text-gray-500">No statistics found for “{trimmedName}”.</p>
	{:else}
		<p class="mt-1 text-sm text-gray-400">Enter a name to look up.</p>
	{/if}
</article>
