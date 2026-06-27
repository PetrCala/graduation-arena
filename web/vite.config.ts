import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// adapter-static gives a fully static build. `fallback` emits an SPA
			// fallback page so client-side routing works without a server.
			adapter: adapter({ fallback: '200.html' }),
			prerender: { entries: ['*'] },
			alias: {
				// Import the shared data contract types from schemas/ts/ without
				// duplicating definitions. See ../schemas/ts/types.ts.
				$schemas: fileURLToPath(new URL('../schemas/ts', import.meta.url))
			}
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
