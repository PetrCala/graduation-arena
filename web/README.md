# web

SvelteKit static site (static adapter) + Tailwind. Read-only: it fetches the precomputed
`EvaluatorStats` JSON and runs the supervisor + opponent lookup **client-side**.

To be initialised in the tooling-baseline issue (K1) via `npm create svelte@latest`. Builds
against mock data conforming to the [schemas](../schemas) contract until real aggregates
exist. Deploys to Firebase Hosting via CI.

See [../docs/app-architecture.md](../docs/app-architecture.md).
