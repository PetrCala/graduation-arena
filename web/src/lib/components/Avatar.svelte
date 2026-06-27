<script lang="ts">
	import { evaluatorInitials } from '$lib/data/evaluators';

	let { name, src = null }: { name: string; src?: string | null } = $props();

	// This component is reused across lookups, so remember which URL failed rather than a
	// plain boolean — when `src` changes to a fresh URL the image is attempted again.
	let failedSrc = $state<string | null>(null);

	const initials = $derived(evaluatorInitials(name));
	const showImage = $derived(!!src && src !== failedSrc);
</script>

{#if showImage}
	<img
		{src}
		alt=""
		onerror={() => (failedSrc = src)}
		class="h-10 w-10 shrink-0 rounded-full object-cover"
	/>
{:else}
	<div
		aria-hidden="true"
		class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-200 text-sm font-semibold text-gray-600"
	>
		{initials}
	</div>
{/if}
