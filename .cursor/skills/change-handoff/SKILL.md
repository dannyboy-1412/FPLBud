---
name: change-handoff
description: Writes the FPLBud close-out after the agent adds a feature or fixes a bug. Covers what changed, why, which code moved, what was already verified, and a concrete checklist of what to test. Use before the final response whenever a task changes behavior in the web app, API, fplcore, ingest, database, or tests. Trigger on feature work, bug fixes, and behavior changes. Skip questions, reviews that do not edit code, and formatting or docs with no behavior change.
---

# Change handoff

Before the final response on a feature or fix, add one handoff block. Base it on the diff and on checks that actually ran. The reader has not seen the tool calls.

This does not authorize a commit, push, or pull request.

## When to run

Run after verification, before the final response, when this task changed behavior in any of:

- `web/`
- `api/`
- `fplcore/`
- `ingest/`
- `db/`
- `tests/`
- `samples/` when a frozen payload now drives different behaviour
- build or workflow config that changes how those packages run

Do not skip because the diff looks small.

Skip when:

- the task was a question, review, or plan and no behavior changed
- the only edits are formatting, comments, or docs with no behavior change
- the user asks to skip the handoff

## Read the diff first

Do not ask the user for a summary. Collect:

- `git status -sb`
- `git diff --stat` and `git diff --stat --cached`
- `git ls-files --others --exclude-standard` (untracked files are missing from `--stat`)
- `git diff` and `git diff --cached` for the paths above, enough to see behavior, not a line-by-line retelling

If the work is already committed on this branch, include `git diff --stat <base>...HEAD` and `git log --oneline <base>..HEAD`. Use `origin/main` when it exists, otherwise `main`.

If nothing eligible changed, do not emit the block.

## Write the block

Put a one-sentence status first, then the block below. Do not repeat the same fact in both.

Lead with the user-visible outcome. For a fix, name the old behavior and the new one. For a feature, name who it is for (guest, signed-in user, or background agent) and what they can do now.

Group paths by package. Name the few paths that carry the behavior. Do not list every touched file.

**Already checked** may only include commands and flows from this session, each with its result. If a check did not run, say it did not run. Do not invent a pass.

**What you should test** is for the user, after you stop. Each item is one action plus the result they should see. Order by risk. Cap the list at the checks that could still be wrong; drop generic padding.

Include a regression on the nearest behavior you did not mean to change: the other horizon, the other auth mode, or the sibling page that shares the component.

Match the list to the paths that moved:

| Paths | Checks to prefer |
|---|---|
| `web/` | The route that changed, then any route that shares its state or components (`/`, `/try/[entryId]`, `/dashboard`, `/squad`, `/plans`, `/insights`, `/chat`, `/settings`). Empty and error states when those renders changed. Desktop and a narrow viewport when layout changed. |
| `api/` | The route as a guest and, when auth matters, as a signed-in user. Then the page that calls it. |
| `fplcore/` metrics, optimiser, rules, agent, chips | `uv run pytest -q` on the touched tests if it has not already passed. A one-gameweek plan, plus a 3- or 5-gameweek plan when horizon or chip logic moved. |
| `fplcore/` chat or explain | One ordinary question and one that should be refused or left unanswered. |
| `db/` | The migration applies, existing reads still return, and a row the user must not see stays hidden. |
| `ingest/` | The changed step upserts the rows it should and leaves unrelated rows in place. |
| `samples/` | The test that loads the fixture still matches the new payload. |

## Not covered

Name residual risk in one or two lines: live FPL data, a signed-in Google session, a deploy, or a browser pass that did not happen. Omit this section when nothing material remains.

## Output

```markdown
## What changed
[1–3 sentences. Outcome first. Fix: old behavior, then new behavior.]

## Where
- `path/` — what that area now does

## Already checked
- `command or flow` — passed, failed, or not run

## What you should test
- [ ] [Action] → [result you should see]
- [ ] [Nearest unchanged neighbor] → [still behaves as before]

## Not covered
[Only if something material was not exercised.]
```

## Example

```markdown
## What changed
Guest plans stay on the next gameweek. A guest request with any other horizon is rejected before the solver runs. Signed-in plans for 3 and 5 gameweeks are unchanged.

## Where
- `api/src/api/routers/suggestions.py` — rejects a guest horizon other than 1
- `tests/` — covers that rejection

## Already checked
- `uv run pytest -q tests/test_suggestions.py` — passed
- Browser — not run; no page changed

## What you should test
- [ ] As a guest, open a public team and ask for the next gameweek → you still get a squad and captain
- [ ] As a guest, ask for three gameweeks → the request is rejected and no plan is saved
- [ ] Signed in, ask for a three-gameweek plan → it still solves

## Not covered
Horizon 5 for a signed-in team was not re-run.
```
