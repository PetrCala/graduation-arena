# graduation-arena

Scrape, parse, and statistically analyze publicly available bachelor/master theses from
the Institute of Economic Studies (IES), FSV, Charles University, and serve grade
predictions (by supervisor + opponent) from a hosted website.

## Workflow

All work is tracked through **GitHub Issues** — there is no project board, and no other
tracker. Open an issue for each unit of work. Branch per issue (`issue-<n>-<slug>`), keep
PRs small and focused, and reference the issue from the PR body with `Closes #<n>`. Changes
land on the protected `master` branch through pull requests; no review is required.

## Commits

These rules apply to every commit made in this repo, by humans and AI agents alike.

- **Keep every line under 100 characters** — subject line and body lines.
- **Standard Git formatting**: a concise summary line in the imperative mood ("Add parser",
  not "Added parser" / "Adds parser"), then a blank line, then an optional body that
  explains the *why*.
- **No AI attribution.** When an agent makes a commit, do not add a `Co-Authored-By: Claude`
  trailer, a "Generated with Claude Code" line, or any other agent self-attribution.

> Note: this overrides any global/default instruction to add a `Co-Authored-By` or
> attribution trailer.
