# web

SvelteKit static site (static adapter) + Tailwind. Read-only: it fetches the precomputed
`EvaluatorStats` JSON and runs the supervisor + opponent lookup **client-side**. Deploys to
Firebase Hosting via CI. See [../docs/app-architecture.md](../docs/app-architecture.md).

## Toolchain

- **SvelteKit** + **TypeScript**, scaffolded with the official `sv create`.
- **`@sveltejs/adapter-static`** — fully static output (prerender + `200.html` SPA fallback).
  Adapter and `kit` options are configured in [`vite.config.ts`](./vite.config.ts); SvelteKit
  2.62+ reads config from there, so there is no `svelte.config.js`.
- **Tailwind CSS** (v4, via `@tailwindcss/vite`; styles in `src/routes/layout.css`).
- **ESLint + Prettier** (`npm run lint`, `npm run format`).
- **Vitest** (`npm run test`).

## Data contract

Types come from the shared contract in [`../schemas/ts/`](../schemas/ts) — never redefined
here. They are imported through the `$schemas` alias (configured in `vite.config.ts`), e.g.
`import type { EvaluatorStats } from '$schemas'`.

## Data access

- Mock aggregates: [`static/data/evaluator-stats.json`](./static/data/evaluator-stats.json)
  (served at `/data/evaluator-stats.json`). Replaced by real pipeline output later.
- Typed loader + lookup: [`src/lib/data/evaluators.ts`](./src/lib/data/evaluators.ts) — loads
  the stats and resolves a supervisor + opponent name pair to their `EvaluatorStats` (tolerant
  matching, graceful not-found). Tests in `src/lib/data/evaluators.spec.ts`.

## Commands

```sh
npm install      # install dependencies
npm run dev      # dev server (add -- --open to launch a browser)
npm run build    # static production build (output in build/)
npm run preview  # preview the production build
npm run lint     # prettier --check + eslint
npm run format   # prettier --write
npm run check    # svelte-check (type-check)
npm run test     # vitest (run once)
```

To recreate the scaffold with the same configuration:

```sh
npx sv create --template minimal --types ts \
  --add eslint prettier vitest="usages:unit" \
  tailwindcss="plugins:typography" sveltekit-adapter="adapter:static" \
  --no-download-check --install npm web
```
