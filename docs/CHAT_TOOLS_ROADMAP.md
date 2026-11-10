# Chat tools roadmap: more accurate, fewer rounds

**What this is:** proposals for new chat tools, upgrades to the existing 13, and a few harness changes that are not tools. The aim is answers that are right more often and arrive in fewer model rounds.
**Basis:** the code on 6 Nov 2026: `api/src/api/chat/tools/*`, `fplcore/src/fplcore/chat/*`, `api/src/api/services.py`, `db/schema.sql`, `evals/chat/cases/*.json` and `docs/CHATBOT_HARNESS_SPEC.md`. Nothing here has been built or measured. Round counts in §3 come from reading the prompt and the tools, not from traces.

---

## 1. Summary

Most of the slowness and most of the errors come from the same root cause. **The tools return raw rows, and the model has to join them or do arithmetic before it can answer.** Two rules then punish that:

- The system prompt forbids the model from doing arithmetic that decides a recommendation.
- `grounding_check` hard-fails any price, points figure or gameweek that is not in this turn's tool results (`fplcore/chat/guard.py`). A delta the model computes itself (5.2 − 3.1 = 2.1) is not in the corpus. It triggers a repair call, and if the repair also fails, the template fallback.

So a question like "is Saka for Palmer worth it over three weeks?" today takes three or four model rounds, and the honest answer is still vague or a fallback.

The fix has three parts, in order of payoff:

1. **Fix the existing tools (§4).** The prompt names arguments that do not exist. Free-text arguments silently fall back to the wrong data. `get_plan_suggestions` throws away chip advice, transfers and the planned XI that are already stored. These are cheap fixes with a direct effect on accuracy.
2. **Add six tools that return the computed answer, not the inputs (§5).** Replacement search, multi-move evaluation with projected deltas and hit cost, captain options, best XI and bench order, a league-wide fixture ticker, and a one-call squad review.
3. **Harness changes (§6).** Resolve player names before the first model call, share one per-turn projection cache across tools, and prefetch obvious intents. Each of these removes a round without adding a tool.

"10x" is not something we can claim yet. The realistic targets for common questions are about half the model rounds, a much lower repair and fallback rate, and no answer that has to guess a number. §2 says how to measure that.

---

## 2. Measure first

`chat_turns` already records `rounds`, `tool_call_count`, `latency_ms`, `first_token_ms`, `status` (`ok` or `fallback`), `repaired` and `grounding_flags`. `chat_tool_calls` records each call's name, arguments, `ok`, `error_code` and duration. Take a baseline before changing anything:

```sql
select date_trunc('day', created_at) as day,
       count(*) as turns,
       avg(rounds) as avg_rounds,
       avg(tool_call_count) as avg_tools,
       percentile_cont(0.5) within group (order by latency_ms) as p50_ms,
       percentile_cont(0.9) within group (order by latency_ms) as p90_ms,
       avg((status = 'fallback')::int) as fallback_rate,
       avg(repaired::int) as repair_rate
  from chat_turns
 where created_at > now() - interval '14 days'
 group by 1 order by 1;

select name, error_code, count(*) as calls, avg(duration_ms) as avg_ms
  from chat_tool_calls
 where created_at > now() - interval '14 days'
 group by 1, 2 order by calls desc;
```

Targets to hold each change against:

| Metric | Target |
|---|---|
| Average rounds per turn | down by about half on the §3 questions |
| Repair rate plus fallback rate | under 5% |
| `INVALID_ARGUMENT` and `UNKNOWN_TOOL` share of calls | under 1% |
| p90 latency | under 8 s, not counting the optimiser |
| `projection` or `price` grounding flags | close to zero on transfer and captain questions |

**Eval gap.** Every case in `evals/chat/cases/core.json` and `plans.json` scripts the tool calls up front, so the suite tests grounding and wording, not whether the model picks the right tool. Each new tool in §5 should come with replay or live cases graded on the tool the model calls and on the final answer (§8).

---

## 3. Where the rounds go today

One round is one full model call over the system prompt, the tool schemas, the context block and the history. Tool calls inside a round already run in parallel (`asyncio.gather` in `loop.py`), so the cost is the round count, not the number of tools.

| Question | Rounds today (expected) | Why | With this roadmap |
|---|---|---|---|
| "Tell me about Salah" | 2–3 | `get_player` needs an id, so `search_players` runs first | 1–2: the name is pre-resolved (§6.1) |
| "Saka or Palmer over the next 3?" | 3–4 | resolve both, `compare_players` is next gameweek only, then `get_fixtures` per club | 2: pre-resolved, then `compare_players(horizon=3)` |
| "Is A for B worth it?" | 3–4, often repaired | `evaluate_transfer` gives legality only, so the model has to subtract projections, which the guard rejects | 2: `evaluate_transfers` returns legality, delta, hit cost and net |
| "Who should replace X?" | 4–6 | search the position, then `evaluate_transfer` on each candidate, then compare | 2: `find_replacements` |
| "Who should I captain?" | 2–3 | the prompt names `get_insights(my_squad, captaincy)`, which does not exist, so the model tries `view="squad"` or another tool | 1–2: `get_captain_options`, or prefetched (§6.3) |
| "Who should I bench?" | 3+ or a guess | no lineup tool, so the model reasons from the context block projections | 2: `get_best_lineup` |
| "When should I wildcard?" | 2–3 | chip advice is stored but `get_plan_suggestions` does not return it | 2: chip advice in `get_plan_suggestions` |
| "Which teams have good fixtures?" | 3+ | `get_fixtures` returns 40 raw rows and blanks and doubles for one club only | 2: `get_fixtures(view="ticker")` |
| "Rate my team / any problems?" | 3–5 | `get_my_team`, `get_insights(squad)`, `get_fixtures` and several lookups | 2: `review_my_squad` |

---

## 4. Fix the existing tools first

These are the cheapest changes with the largest effect on accuracy. Do them before adding anything.

### 4.1 Prompt and schema mismatches

The playbooks in `fplcore/chat/prompt.py` call tools with arguments that do not exist:

| Prompt says | Code has | Effect |
|---|---|---|
| `get_insights(my_squad, captaincy)` | `get_insights(view: str)`, where `"squad"` returns captaincy among other things | The model guesses `view`. A wrong guess falls back to `in_form` with no error |
| `get_fixtures(blanks_doubles)` | `get_fixtures(team_id, gameweeks)`. Blanks and doubles are only filled when `team_id` is set | A league-wide blank or double question gets an empty `blanks` list. That reads as "no blanks" |

Rewrite the playbooks against the real schemas, and add a test that every `name(arg)` written in `SYSTEM_PROMPT` matches a registered tool and argument.

### 4.2 Make free-text arguments enums

`get_insights.view`, `get_market_movers.kind`, `explain_topic.topic` and `save_preference.key` are typed `str`. The strict JSON schema therefore does not constrain them. Worse, `get_insights` maps an unknown view to `in_form`, and `get_market_movers` maps an unknown kind to the default lists. The result looks grounded but answers a different question.

Use `Literal[...]` so `strict_schema` emits an `enum`, and return `INVALID_ARGUMENT` with the valid values instead of falling back.

### 4.3 `get_plan_suggestions` drops stored data

`agent_suggestions` stores `plan` (transfers with `metric_deltas`, the XI, bench, captain, vice and `projected_points_by_gw`), `alternatives`, `chip_advice` and `reason_codes`. The tool returns only `headline`, `hits`, `gain_vs_roll` and the first 400 characters of `explanation`. The prompt then tells the model to "use plan chip advice", which it has never been given.

Return, per horizon:

- `transfers`: up to 4, each with names, ids, `cost_delta_m` and the top two `metric_deltas`
- `captain_id`, `vice_id`, and the XI and bench ids (names come from context)
- `projected_points_by_gw` and `bank_after_m`
- `alternatives`: the roll plan and the fewer-transfer plan, with their projected totals
- `chip_advice`: chip, `recommend`, `best_gw`, `expected_gain` and `expires_soon`
- `reason_codes`

This answers "what should I do", "why", "what about rolling" and "when should I chip" from one call that is already memoised.

### 4.4 Smaller fixes

| Tool | Problem | Fix |
|---|---|---|
| `get_player` | Calls `ranked_players` over every player to read one projection. Drops xG and xA from the history `player_detail` already loaded. Next gameweek only | Add `horizon` (1–5) and per-gameweek projections with opponent and FDR. Keep xG and xA in `recent`. Read from the per-turn cache (§6.2) |
| `compare_players` | Next gameweek only. No fixtures, minutes or form, so the model follows up with `get_fixtures` and `get_player` | Add `horizon`, per-gameweek projections, fixtures and the component scores (form, fixture, xGI, minutes) so "why" is answerable |
| `search_players` | Plain substring match on `web_name`. "Odegaard" does not match "Ødegaard", and first and second names are ignored. Next gameweek only | Accent-fold, match `first_name` and `second_name`, and add `horizon` and `sort` (`proj`, `price`, `ownership`, `form`) |
| `get_insights(view="availability")` | Returns only the user's own squad flags, so "who's injured?" gets the wrong scope | Add a league-wide flag list (status `d`, `i`, `s` and `u`, with chance and news) and keep the squad list as a separate view |
| `get_my_team` | Next-gameweek projection only | Add projected points for the next three gameweeks per player |
| Most tools | `as_of=None`, so the "Data as of" line depends on the context block | Set `as_of` from `player_metrics.computed_at` or the latest `ingest_runs` row |

---

## 5. New tools

Each tool follows the existing conventions: a pydantic model with `extra="forbid"`, identity from `ToolContext`, money in £m, compact names plus ids, and `ok: false` errors with a hint. The common rule is that **every number the model needs to say comes back from the tool already computed**, so the guard has nothing to reject.

### N1 `evaluate_transfers` (replaces `evaluate_transfer`)

*Answers:* "Is A for B worth it?", "Should I take a −4 for this?", "A and B out for C and D?"

```python
class Move(BaseModel):
    out_player_id: int
    in_player_id: int

class EvaluateTransfersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    moves: list[Move] = Field(min_length=1, max_length=3)
    horizon: Literal[1, 3, 5]
```

*Wraps:* `rules.check_transfer` for each move, applied in order (bank and club counts update after each), then `load_opt_players` for projections over the horizon.

*Returns:* per move, `legal`, `code`, `message`, the projection out and in, and `delta`. Overall: `total_delta`, `free_transfers_used`, `hits`, `hit_cost`, `net_after_hits`, `bank_after_m`, and `verdict` (`worth_it`, `marginal` or `not_worth_it`), using the same `4 + hit_margin` rule as `HORIZON_SETTINGS` in `optimise.py`.

*Why:* this is the main source of model arithmetic today. It also stops the model treating "legal" as "good".

### N2 `find_replacements`

*Answers:* "Who should replace Salah?", "Best midfielder for Gordon under £7m?"

```python
class ReplacementArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    out_player_id: int
    horizon: Literal[1, 3, 5]
    max_price_m: float | None = None
    limit: int | None = Field(default=None, ge=1, le=5)
```

*Wraps:* `load_opt_players` for the user's snapshot. Candidates are filtered to the same position, `can_in`, not already owned, the three-per-club rule after the sale, and price at most the selling price plus the bank (or `max_price_m` if lower). They are ranked by projected gain over the horizon.

*Returns:* `budget_m` (selling price plus bank), and per candidate: id, name, club, price, projection, `delta_vs_out`, ownership, status and the next three fixtures. A note says when fewer than `limit` are affordable.

*Why:* today this takes one search plus one `evaluate_transfer` per candidate, and the model still has to compare them.

### N3 `get_captain_options`

*Answers:* "Who should I captain?", "Triple Captain this week?"

*Arguments:* none.

*Wraps:* `squad_stats_payload(...)["captaincy"]` (`captaincy_board`), the saved plan's `captain_id`, and `latest_crowd_captain`.

*Returns:* the top 3–5 starters by next-gameweek projection, each with fixture or fixtures (a double shows both), home or away, FDR, minutes score, chance of playing and ownership. Also the plan's captain and vice, the crowd's most-captained player, `captain_margin` (first minus second), and `triple_captain` advice from `chip_advice` when that chip is available.

*Why:* captaincy is the most common FPL question, and the current route depends on guessing a `get_insights` view.

### N4 `get_best_lineup`

*Answers:* "Who should I bench?", "Is my bench order right?", "Should I start X or Y?"

*Arguments:* none.

*Wraps:* the `suggested_lineups` cache for this user, entry, gameweek and squad hash. On a miss, `lineup_from_optimiser` over `load_opt_players`, with zero transfers and no model call. The chat must not call `choose_lineup` (that one uses web search, see §7).

*Returns:* the XI with formation, bench order with projections, captain and vice, and `changes_vs_current`: which starters and bench players differ from the published picks, each with the projection difference the optimiser saw.

### N5 `get_fixtures(view="ticker")` (a mode on the existing tool)

*Answers:* "Which teams have the best fixtures?", "Who blanks in GW 31?", "Any doubles coming?"

Rather than a new tool, add `view: Literal["team", "ticker"]` and `gameweeks` (1–6, default the next 5).

*Wraps:* `fixtures_for` plus the per-team `fixture_score` that is already in `player_metrics`.

*Returns, for `ticker`:* all 20 clubs sorted by average ease over the window, each with per-gameweek opponents and FDR, plus league-wide `blanks` and `doubles` maps of gameweek to clubs.

*Why:* fixes the "empty `blanks` means no blanks" problem in §4.1 and replaces 40 raw rows with an answer.

### N6 `review_my_squad`

*Answers:* "Rate my team", "Any problems in my squad?", "What should I worry about this week?"

*Arguments:* none.

*Wraps:* `compute_squad_score` (the 0–10 squad score already used on the dashboard), squad flags, blank and double exposure from `fixtures_for` over the next three gameweeks, and the `find_replacements` internals for the two weakest starters.

*Returns:* `squad_score`, flagged players with status and chance, the number of starters blanking or doubling per gameweek, the two weakest starters each with the best affordable replacement and `delta`, bench problems from N4's `changes_vs_current`, and `template_threats` from `squad_stats_payload`.

*Why:* one call instead of three to five for the most open-ended question users ask. Results stay small because every list is capped at three.

### Tool count

This takes the catalog from 13 to 18 tools (N1 replaces one and N5 is a mode). Tool schemas are re-sent on every round. Measure prompt tokens and `cached_tokens` before and after, and keep the tool order stable so provider prompt caching still hits. If evals show two tools getting confused more than about 10% of the time (spec §6.5), merge them. The first candidate is `review_my_squad` into `get_my_team(detail="review")`.

---

## 6. Harness changes that are not tools

### 6.1 Resolve player names before the first round

The biggest single speed win. Before calling the model, match the user's message against player names (accent-folded `web_name`, `second_name`, and a small nickname table such as "KDB" and "Trent"). Append a data-only line to the context block:

```
MENTIONED: 13 Haaland MCI FWD £15.0m | 20 Saka ARS MID £10.1m | AMBIGUOUS "Martinelli": 12 ARS, 412 BRE
```

The model can then call id-based tools in round one. Those ids also enter `corpus.player_ids`, so `[[p:ID|Name]]` chips are allowed.

A tool fallback for cases the pre-pass misses: `resolve_players(names: list[str] ≤ 5)`, which returns the best match per name or `PLAYER_AMBIGUOUS` with candidates. That error code is already in the spec vocabulary but never emitted.

### 6.2 One projection cache per turn

`ranked_players` runs a join over every player and recomputes projections in Python. It is called by `build_context` and by `search_players`, `get_player`, `compare_players`, `get_insights` and `squad_stats_payload`, often several times per turn. `squad_stats_payload` alone calls it twice. The registry memo is keyed by tool name and arguments, so it does not help across tools.

Add a per-turn cache keyed by `(weights hash, horizon, data_version)`. It can be a dict on a turn-scoped object passed to handlers next to `ctx`, so `ToolContext` stays plain data. All tools read from it. Do the same for `load_opt_players`, which N1, N2, N4 and N6 share.

### 6.3 Prefetch obvious intents

A few intents are unambiguous from keywords: captain, bench or lineup, deadline, wildcard or chip, "rate my team". For those, run the matching tool before the first round and put its result in the conversation as a completed tool call. The model starts round one with the data. Rules:

- Prefetch at most one tool, and only read-only tools that need no arguments (N3, N4, N6, `get_plan_suggestions`).
- It counts toward the turn's tool cap and is recorded in `chat_tool_calls` like any other call.
- Measure it against the eval suite. Drop any prefetch whose result the model ignores more than about a third of the time.

### 6.4 Prompt updates that go with the tools

- Replace the playbooks with one line per intent naming the exact call, for example `Captain: get_captain_options.` and `Swap A for B: evaluate_transfers(moves=[...], horizon=3).`
- Add: "If a figure you want to state is not in a tool result, call the tool that computes it. Do not derive it."
- Drop `explain_topic(chip_advice)` and other names that no longer exist, and keep the test from §4.1.

---

## 7. Deliberately not adding

| Idea | Why not |
|---|---|
| Web search or live team news | Completes the lethal trifecta: private squad, untrusted text, and an outbound channel (spec §12). `choose_lineup` uses web search, which is why N4 uses `lineup_from_optimiser` instead |
| Live gameweek points | `event/{gw}/live` is not ingested. A tool would have nothing to read |
| Rival or mini-league analysis | Needs other managers' entries. That is a product and privacy decision first |
| A model-written "what-if" simulator | Points have to come from the optimiser and the projection maths, not the model |
| A planner/verifier multi-agent split | Costs several times the tokens for questions that share one squad context (spec P3). Revisit only if evals show the single loop failing |
| `get_predictions` and `get_squad_rating` | Already planned in `FEATURE_SPEC_AI_TRANSFERS.md` behind the prediction model. When that ships, these should be fields on `get_player`, `compare_players` and N6, not new tools |

---

## 8. Rollout order

Each step ships with its eval cases and is compared against the §2 baseline.

| Step | Work | Expected effect |
|---|---|---|
| 1 | §4.1 prompt fixes and test, §4.2 enums | Fewer invalid and misrouted calls. Smallest change, do it first |
| 2 | §4.3 `get_plan_suggestions` returns the stored plan | Chip, "why" and "roll instead?" questions answered in one call |
| 3 | §6.2 per-turn projection cache | Lower tool latency. Nothing changes for the model |
| 4 | N1 `evaluate_transfers` | Removes the main source of model arithmetic and repairs |
| 5 | §6.1 name pre-resolution and `resolve_players` | One round fewer on any question that names a player |
| 6 | N3 captain, N4 lineup | The two most common weekly questions |
| 7 | N2 replacements, N5 ticker | Transfer research without the search-and-check loop |
| 8 | N6 squad review, §6.3 prefetch | Open-ended questions in two rounds |
| 9 | §4.4 smaller fixes | Better "why" answers and correct injury scope |

### Eval cases to add

At least two cases per tool: one where the model should call it, and one where it should not, for example `get_captain_options` should not run for a transfer question. Grade the tool called, the arguments, and the final answer.

- Swap A for B over 3 gameweeks, with a positive delta and no hit → `evaluate_transfers`, verdict `worth_it`, and the delta quoted exactly.
- Two moves with one free transfer → `hits: 1`, and net after the hit quoted from the tool.
- "Replace Salah under £8m" when nothing is affordable → `find_replacements` returns a short list with its note, and the answer says so.
- "Who blanks in GW N?" with several clubs blanking → `get_fixtures(view="ticker")`, and every blanking club named.
- "Ødegaard or Odegaard" spelling → resolved to the same id with no search round.
- An ambiguous surname → one short clarifying question listing the candidates.
- "When should I wildcard?" → chip advice quoted from `get_plan_suggestions` and called a heuristic.
- An unknown `get_insights` view → `INVALID_ARGUMENT`, not `in_form` data.
