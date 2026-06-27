# Deploy

The web app (`web/`) is a static SvelteKit build served from **Firebase Hosting**. CI builds
and deploys it via [`.github/workflows/deploy-web.yml`](../.github/workflows/deploy-web.yml):

- **push to `master`** → deploy to the live (production) channel
- **pull request** → deploy to an ephemeral per-PR preview channel; the URL is posted as a
  PR comment

Hosting config lives at the repo root: [`firebase.json`](../firebase.json) (publish dir
`web/build`, SPA fallback to `200.html`) and [`.firebaserc`](../.firebaserc) (the `default`
project alias).

## One-time manual setup (owner: @PetrCala)

The workflow builds on every run, but the **deploy steps stay skipped until the secret below
exists** — so CI is green now and starts deploying automatically once setup is done.

1. **Create / choose the Firebase project** in the [Firebase console](https://console.firebase.google.com/),
   then enable Hosting for it.
2. **Set the project id** in [`.firebaserc`](../.firebaserc): replace `graduation-arena` under
   `projects.default` with the real project id (the workflow passes `projectId: default`,
   which resolves from this file).
3. **Create a deploy service account** and add it as a repo secret named
   **`FIREBASE_SERVICE_ACCOUNT`**:

   ```sh
   # from the repo root, logged in to the right Google account:
   npm i -g firebase-tools
   firebase login
   firebase init hosting:github      # generates the SA + sets the secret for you
   ```

   Or do it by hand: create a service account with the _Firebase Hosting Admin_ role in the
   Google Cloud console, download its JSON key, and add it under
   **Settings → Secrets and variables → Actions → New repository secret** as
   `FIREBASE_SERVICE_ACCOUNT` (paste the full JSON).

That's it — the next push to `master` (or any PR) will deploy.

## Local

```sh
cd web && npm install && npm run build   # outputs web/build/
firebase hosting:channel:deploy preview  # optional manual preview (needs firebase-tools + auth)
firebase deploy --only hosting           # manual production deploy
```
