---
name: publish-pr
description: >-
  Publishes FPLBud changes on a branch and a pull request. The pull request
  is plain language: what changed, the security analyst's remarks, and
  before-and-after screenshots only when the visual change is large. Use
  when the user asks to push, ship, land, or publish code changes, or to
  open a pull request. Do not push those commits straight to main.
---

# Publish a pull request

New work goes on a branch and a pull request against `main`. Write the pull request for someone who has not seen the chat. Do not push that work straight to `main`.

The remote is `origin` (`dannyboy-1412/FPLBud`). The shell is PowerShell: chain commands with `;`.

## When this applies

Use this when the user asks to push, ship, land, or publish changes, or to open a pull request.

A bare "push" means this workflow. It does not mean `git push origin main`.

Skip when there is nothing to publish, the user says to push to `main` or to skip the pull request, or the task is a question and no commit was requested.

## Order

1. Security review, if this change does not already have one.
2. Commit, on the right branch.
3. Screenshots, only when the visual change is big.
4. Push, then open or update the pull request.

## Security review

The pull request includes the security analyst's remarks for this change.

If this session already has the report, use it. If it does not, follow `.cursor/skills/feature-security-review/SKILL.md` before the commit, so a fix lands in the commit.

In the body, write what the analyst concluded. Plain sentences.

- No issues: "Security review found no issues." Then what was checked, in one sentence.
- Each finding: severity, `file:line`, and what a user or attacker can do. For an unintended logic change, say what it did before and what it does now.

Do not paste the analyst's prompt or the diff. Do not drop a finding. Do not call a finding fixed unless you fixed it and a second review agreed.

## Commit

In parallel, read `git status`, `git diff`, `git diff --cached`, `git log -8 --oneline`, and `git rev-parse --abbrev-ref HEAD`. If the branch tracks a remote, compare it with `origin/main`.

Commit only the files in this change. Leave `.firecrawl/` and secrets untracked. Do not update git config, skip hooks, or force-push.

Subject: one imperative sentence, about why, in the style of recent history.

## Branch

| Starting point | What to do |
|---|---|
| `main`, changes not committed | `git checkout -b <name>` before the commit. `main` stays at `origin/main`. |
| `main`, commits not pushed | Point a new branch at `HEAD` (`git branch <name>`), push it, open the pull request, then return local `main` with `git switch main` and `git reset --keep origin/main`. Only after the branch is on `origin` and the worktree is clean. |
| Any other branch | Stay on it. Do not cut a second branch. |

Name it from the change, short kebab-case (`insights-decision-board`). Not `update`, `fix`, or `changes` on their own.

## Screenshots

Add a before and an after only when a reviewer needs the picture. That is a new page, a redesigned screen, or a new layout on `/`, `/try/[entryId]`, `/dashboard` (plans, squad, insights), `/chat`, `/onboarding`, or `/settings`.

Leave them out for copy, color, spacing, a small control move, a change outside `web/`, or a fix that restores the old screen. Omit the section. Do not write that there is no screenshot.

One pair for the screen that changed. Add a second pair only when a different page changed too.

1. Shoot the new screen on this branch with the browser tools. Start `pnpm dev` in `web/` when it is not already running.
2. Shoot the same route on `origin/main` without leaving this branch. `git worktree add` a temp directory at `origin/main`, run that copy on another port, shoot, then `git worktree remove` the temp directory.
3. Same viewport for both. Desktop, unless the change is the narrow layout.
4. Save the files outside the repo. Do not commit them.
5. If the screen needs a sign-in you do not have, say that in the body and skip the picture. An error page is not the before or after.

## Open the pull request

Push with `git push -u origin HEAD`.

If `gh pr view --json url` already returns a pull request, push and update the body. Do not open another.

Write the body to a temp file. Use the same image path in the markdown and in `--attach`, so GitHub rewrites it to an uploaded URL.

```powershell
gh pr create --base main --title "the outcome, in one line" --body-file $body --attach $before --attach $after
```

Drop `--attach` when there are no screenshots. For an existing pull request, `gh pr edit --body-file $body` with the same attach flags.

```markdown
## What this does

<Who it is for, what they can do now, and why. Two or three sentences.>

## Security review

Security review found no issues. Guest suggestions stay on the next gameweek, and signed-in plans were not part of this change.

## Before and after

**Before**

![Plans page before this change](<before-path>)

**After**

![Plans page on this branch](<after-path>)

<One sentence on what the pictures show.>

## How to check

- [ ] <one action, and what you should see>
```

Omit "Before and after" when there are no screenshots. Replace the security example with this change's real remarks.

If this `gh` rejects `--attach`, publish the text. Say that the CLI cannot upload images, and where the files are. Do not commit them to invent a URL.

Return the pull request URL.

## Do not

- `git push origin main` for new work
- force-push `main`
- merge unless the user asks
- commit the screenshots or the body file
