---
name: publish-pr
description: >-
  Publishes FPLBud changes on a new branch and a pull request. Use when the
  user asks to push, ship, land, or publish code changes, or to open a pull
  request. Do not push those commits straight to main.
---

# Branch and pull request

New commits go out on a branch and a pull request against `main`.

This repo's remote is `origin` (`dannyboy-1412/FPLBud`). The shell is PowerShell: chain commands with `;`, not `&&`. Pass commit messages and pull request bodies with a here-string.

## When this applies

Apply when the user asks to push, ship, land, or publish changes, or to open a pull request.

Skip when:

- there is nothing to publish
- the user explicitly says to push to `main`, or to skip the pull request
- the task is a question and no commit was requested

A bare "push" is this workflow. It is not `git push origin main`.

## Before publishing

In parallel:

- `git status`
- `git diff` and `git diff --cached`
- `git log -8 --oneline`
- `git rev-parse --abbrev-ref HEAD`
- `git status -sb` against `origin/main` (`git rev-parse @{upstream}` when a branch already tracks a remote)

Commit only the files that belong to the change. Leave tool caches (`.firecrawl/`) and secrets untracked. Do not update git config, skip hooks, or force-push.

Commit subjects match recent history: one sentence, imperative, about why.

## Branch

| Starting point | Action |
|---|---|
| `main` with uncommitted changes | `git checkout -b <name>` before the commit. `main` stays at `origin/main`. |
| `main` with unpushed commits | Point a new branch at `HEAD` (`git branch <name>`), push that branch, open the pull request, then return local `main` to `origin/main` with `git switch main` and `git reset --keep origin/main`. Do this only after the branch is on `origin` and the worktree is clean. |
| Any other branch | Stay on it. Do not cut a second branch. |

Name the branch from the change, short and kebab-case (`insights-decision-board`). Do not use `update`, `fix`, or `changes` alone.

## Pull request

Push with `git push -u origin HEAD`.

If `gh pr view --json url` already returns a pull request for this branch, push the new commits and stop. Do not open a second pull request.

Otherwise create one against `main`:

```powershell
gh pr create --base main --title "the pr title" --body @"
## Summary
- <why this change exists>

## Test plan
- [ ] <what to check>

"@
```

Return the pull request URL.

## Do not

- `git push origin main` for new work
- force-push `main`
- merge the pull request unless the user asks
