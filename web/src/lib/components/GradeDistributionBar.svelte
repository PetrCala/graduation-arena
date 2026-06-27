<script lang="ts">
	import type { EvaluatorStats } from '$schemas';
	import { gradeBreakdown } from '$lib/data/evaluators';

	let { stats }: { stats: EvaluatorStats } = $props();

	const rows = $derived(gradeBreakdown(stats));

	// Grayscale ramp: the better the grade the lighter the segment, so a darker bar
	// reads as a stricter grader at a glance. Grades outside 1–4 fall back to mid-gray.
	const SHADE: Record<string, string> = {
		'1': 'bg-gray-300',
		'2': 'bg-gray-500',
		'3': 'bg-gray-700',
		'4': 'bg-gray-900'
	};

	const pct = (p: number) => `${Math.round(p * 100)}%`;
	const label = $derived(rows.map((r) => `grade ${r.grade} ${pct(r.probability)}`).join(', '));
</script>

{#if rows.length > 0}
	<div
		class="flex h-2.5 w-28 overflow-hidden rounded border border-gray-200"
		role="img"
		aria-label={`Grade distribution: ${label}`}
	>
		{#each rows as row (row.grade)}
			<div
				class={SHADE[row.grade] ?? 'bg-gray-400'}
				style="width: {row.probability * 100}%"
				title={`Grade ${row.grade}: ${pct(row.probability)} (n=${row.count})`}
			></div>
		{/each}
	</div>
{:else}
	<span class="text-xs text-gray-400">—</span>
{/if}
