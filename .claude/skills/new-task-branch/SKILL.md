---
name: new-task-branch
description: Start a new non-trivial unit of work on this repo (new source, behavior change, multi-step bug fix) on a fresh branch off main instead of committing straight to main. Use at the start of such a task; skip it for trivial one-line fixes or when the user says to just commit to main.
---

# Starting a new task on this repo

`main` is live: the GitHub Actions workflow commits `state.json` back to
`main` on every scheduled run, and anyone using this repo as a template is
running whatever is on `main`. Small, low-risk changes (a typo fix, a
one-line README tweak, a config value) are fine directly on `main`. Anything
bigger — a new source, a behavior change, a fix that touches multiple
functions — should happen on a branch so `main` always stays known-good.

## Steps

1. `git status` — if there are uncommitted changes unrelated to the new
   task, stop and ask the user how to handle them before branching.
2. Sync `main` first, don't branch off a stale local copy:
   ```
   git fetch origin
   git checkout main
   git pull origin main --ff-only
   ```
3. Create the branch with a short, specific, kebab-case slug describing the
   task (not a ticket number — there's no tracker here):
   ```
   git checkout -b task/<short-kebab-slug>
   ```
   e.g. `task/fix-remoteok-tag-filter`, `task/add-linkedin-source`.
4. Do the work, committing normally on the branch as usual.
5. When the task is done, tell the user what changed and ask how they want
   it landed — fast-forward merge to `main` directly, or a PR via
   `gh pr create` for review first. Don't merge or push `main` without
   asking, same as any other push per the global git safety rules.

## When NOT to use this

- Trivial doc/README typo fixes.
- `state.json` changes from local test runs — those get reverted or
  reconciled via rebase, never branched (see CLAUDE.md's "Working on this
  repo" section).
- Whenever the user explicitly says to just commit to `main`.
