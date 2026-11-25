---
name: feature-security-review
description: >-
  Reviews a finished FPLBud change for security issues and for edits that
  alter existing behavior the feature did not need to change. Use after a
  feature, bug fix, or other behavior change, before the final response.
  Launches a separate security analyst with the feature intent only; the
  analyst reads the diff and surrounding code itself. Covers guest and
  signed-in access, JWT, row level security, horizons, the chat guard, and
  ordinary vulnerabilities. Skip questions, plans, reviews that do not edit
  code, and formatting or docs with no behavior change.
---

# Feature security review

After a behavior change, before the change handoff and before the final response, launch one security analyst. The analyst decides whether this change moves existing behavior it did not need to touch, and whether the diff introduces a vulnerability.

The analyst has not seen this conversation. It does not edit files. Do not review the diff yourself before launching it.

## When to run

Run when this task changed behavior in any of:

- `web/`
- `api/`
- `fplcore/`
- `ingest/`
- `db/`
- `tui/`
- `tests/` when the test locks in that behavior
- workflow config that changes how those packages run

Skip when:

- the task was a question, review, or plan and nothing was edited
- the only edits are formatting, comments, or docs
- the user asks to skip the security review
- you are the analyst (do not launch another one)

## Feature brief

Tell the analyst who the feature is for and what it should do. Write the brief from the user's request. If an earlier message in this chat described the implementation, leave that out. The analyst only sees the prompt you send.

Include only:

- who it is for (guest, signed-in user, background agent, or a named screen)
- what they can do when it works
- the outcome that was asked for
- user-visible behavior that must stay as it was

Do not include files, functions, diffs, code quotes, test names, tool output, or how the solution works.

## Launch

Launch exactly one `generalPurpose` subagent with the Task tool. `run_in_background: false`. In Multitask Mode the tool requires a background run: start it, end the turn without a final response, and continue from "After the report" when the result arrives. Description: `Security analyst`. Do not set a model.

Use this prompt. Fill in the brief. Add nothing else.

```text
You are a security analyst reviewing a FPLBud change. You do not know how it was implemented. Do not ask for the implementation.

Read and follow .cursor/skills/feature-security-review/REVIEW.md.

Repository: <absolute repository path>

Feature:
- Who:
- What they can do:
- Outcome:
- Must stay the same:

Return only the report REVIEW.md specifies. Do not edit files.
```

If the launch fails because the prompt was malformed, correct it and try once. Any other failure: retry once with the same prompt. If it fails again, say the security review did not finish and include the short error. Do not invent a pass.

## After the report

The analyst does not change code. You decide what to do with the findings.

- No findings: one line in the final response. The security review found no issues.
- You agree it is an unintended logic change, or a critical or high security issue this change introduced: fix that finding only. Do not widen the fix. Launch the analyst once more with the same brief, then stop.
- You do not agree: leave the code, and say why in the response.
- Anything still open goes in the final response. Use one table per group that has rows, highest severity first, columns Severity, Location (`file:line`), Finding.

Do not commit, push, or open a pull request from this review. Keep the report. The pull request repeats it in plain language.
