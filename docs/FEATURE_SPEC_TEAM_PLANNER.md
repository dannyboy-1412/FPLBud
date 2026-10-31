# Feature spec: Team & Chip Planner (multi-gameweek scenario planner)

*Draft 1, 31 Oct 2026 (Sydney). Status: proposal. Owner: Daniel.*

**Related documents**
- Rival evidence: [`RIVAL_ANALYSIS_FFHUB.md`](RIVAL_ANALYSIS_FFHUB.md) §3–4.2.
- Depends on: [`FEATURE_SPEC_AI_TRANSFERS.md`](FEATURE_SPEC_AI_TRANSFERS.md), for `player_predictions` (xPts per GW).
- Builds on: `docs/ARCHITECTURE.md` §5 (MILP), §6A (agent, chips), §2A (tiers, where a "multi-GW chip planner" is already listed as a future paid item); `db/schema.sql`; [`CHATBOT_HARNESS_SPEC.md`](CHATBOT_HARNESS_SPEC.md).

---

## 1. Problem and user value

**What FPL managers plan for.** They plan weeks ahead. They:
- bank free transfers for a double gameweek;
- line up a fixture swing;
- time a wildcard before a Bench Boost;
- pick between two Triple Captain weeks.

Chips now come in **two sets per season** (one of each in GW1–19, another in GW20–38; ARCHITECTURE §1), so chip timing matters twice a season.

**What FPLBud does today.**
- The agent produces 1/3/5-GW plans, but **it only decides this week's transfers and then holds the squad** (ARCHITECTURE §6A.3: "Planning future transfers across several GWs is a later enhancement").
- Chip advice is rule-based and per horizon.
- Users can't say "what if I bring in Salah in GW12 and Wildcard in GW14?", and see the consequences.

**Planner value**
1. **See the future squad.** A per-GW pitch for the next 8 GWs, with xPts, bank, free transfers and hits tracked correctly.
2. **Draft scenarios.** Users enter transfers in any future GW, place chips, set lineups and captains, and compare up to 3 drafts side by side.
3. **Solver assist.** "Fill the gaps" runs a true **multi-period optimiser**: transfers in future GWs, FT banking, chips, and user locks such as "must buy X by GW12".
4. **Chip scan.** For each remaining chip, find the best GW and its expected gain, given the user's plan.

## 2. What the rival does (cited)

- **Tier placement.** FFH lists "Team and chip planning" in its cheapest paid tier, Starter. Sources: the [/join](https://www.fantasyfootballhub.co.uk/join) comparison table (31 Oct 2026); the [Freshdesk tiers article](https://fantasyfootballhub.freshdesk.com/support/solutions/articles/103000409131-what-are-the-differences-between-the-starter-pro-ultra-plans-).
- **Pro adds** "Ben Crellin's planning sheet", which is a fixture and planning spreadsheet by a known community figure, and a "Fixture analyser".
- **Play Store wording.** The listing describes "Long-Term Team Planning through interactive scenario modelling of future transfers" ([Play Store](https://play.google.com/store/apps/details?id=uk.co.fantasyfootballhub.app)).
- **What users say**
  - "I could see some predicted points while also going forward in time to see how my team would shape up in the future". The same user regrets this was removed from free use ([R4](https://www.reddit.com/r/FantasyPL/comments/1m8apu1/what_websites_to_use/)).
  - A user wanting to replace Hub asks for "a planner to check how your team looks on future gameweeks" and "a decent fixture ticker" ([R5](https://www.reddit.com/r/FantasyPL/comments/1mq6oq1/alternative_to_hub_and_scout/)).
  - Trustpilot reviewers credit "the team planner" and the "'My Team' planner" (T2, T3). A negative reviewer still liked "squads players at a glance for next 3 weeks" (T4).
- **Not verified.** I couldn't verify whether FFH's planner has a solver that plans future-GW transfers automatically, or whether it only evaluates manual drafts. The tool is behind login.

**Free competitors users mention:** fpl.team and FPL Review's free planner (R4, R5, R8). The bar for a *basic* planner is therefore "free". The paid value has to be the solver and chip intelligence.

## 3. FPLBud approach and differentiation

| | Typical planner (FFH, free tools) | FPLBud planner |
|---|---|---|
| Projections | Vendor points model | Our xPts (sibling spec), with **ranges** and published accuracy |
| Planning | Manual drafting; FFH solver capability unknown | Manual drafting **plus a multi-period MILP** that fills or finishes a plan around user locks |
| FT and bank accounting | Varies | Exact FPL rules from `team_snapshots`: FT banking cap, selling-price rule (50% of profit) for current players, no-cost moves under WC/FH, and FH squad reversion |
| Chips | Place manually | **Chip scan**: the best GW for each remaining chip, its expected gain, and a "use it or lose it" warning before each half's `stop_event` |
| Explanations | – | Per-GW reason codes, and a "Why this plan beats doing nothing" diff. The chatbot can discuss and edit the plan. |
| Agent integration | – | One click **forks the agent's 3/5-GW plan into a draft**. Drafts are re-evaluated automatically when predictions update ("your GW12 plan lost 1.8 xPts after Saka's injury news"). |
| Fixture ticker | FDR colours (Pro "fixture analyser") | A ticker using **model-based difficulty**: the opponent's fitted attack and defence (`team_strengths`), with FDR as a fallback. Free for everyone. |

## 4. User stories

1. As a signed-in user, I can open the planner and see my current squad laid out across GW+1…GW+8, with per-GW xPts, bank and free transfers.
2. As a user, I can make a transfer in any future GW. The planner updates bank, FTs and hits for that GW and every later one, and flags invalid states (over budget, >3 per club, wrong formation).
3. As a user, I can place a chip in a GW. Wildcard and Free Hit make transfers free that week, and Free Hit reverts the squad afterwards. Bench Boost and Triple Captain change that GW's scoring. I see the gain against the same plan without the chip.
4. As a user, I can lock things ("keep Haaland", "buy Palmer in GW12", "no hits", "WC in GW14") and press **Optimise rest of plan**. The solver fills all other transfers and lineups.
5. As a user, I can run a **chip scan** and get "Bench Boost: GW15 (+9.2 xPts, double GW for 3 bench players); hold Triple Captain until GW16 (+5.1)".
6. As a user, I can keep up to 3 named drafts (free: 1) and compare their totals per GW.
7. As a user, I'm told when a draft's expected value changes materially after new data, and why.
8. As a user, I can ask the chatbot "what if I wildcard in GW14 instead of GW13?". It runs the evaluator and answers with the numbers.
9. As a guest, I can try the planner for my team ID in **read-only** mode: the next 3 GWs, the holding squad and the ticker. Saving drafts and the solver need sign-in.

## 5. UX and pages

**Placement:** a new section, `/dashboard?section=planner`, next to Plans / My squad / My season / Market / Insights. On mobile it is a full-screen view.

**Layout**

1. **GW timeline strip** (top). Chips GW+1 … GW+8. Each shows:
   - xPts for the GW;
   - FT available → used;
   - hits;
   - bank;
   - a chip badge.

   Click a chip to focus that GW. DGW and BGW markers come from `fixtures`.
2. **Pitch for the focused GW** (centre). Uses the existing pitch component.
   - Each player shows xPts for that GW, a range bar, and the opponent(s).
   - Click a player to open the "transfer out" drawer: search players by position, sorted by **xPts over the remaining planned GWs**, filtered by affordable price. A comparison row shows the incoming player against the outgoing one per GW.
   - The bench order and captain/vice are editable. They default to auto (existing `lineup.py`).
3. **Chip row.** Remaining chips for each half. Drag onto a GW. "Scan" button. Expiry warnings appear when `stop_event − current GW ≤ 3`.
4. **Fixture ticker** (bottom, collapsible).
   - Squad players' teams plus any searched team, for the next 8 GWs.
   - Cells are coloured by model difficulty, with a toggle to FPL FDR. DGW cells are split and blanks are greyed.
5. **Summary panel** (right; a sheet on mobile).
   - Total xPts (discounted and raw).
   - Comparisons: "vs Do nothing" and "vs Agent plan (N=5)".
   - Validation issues.
   - Buttons: **Optimise rest of plan**, **Chip scan**, **Fork agent plan**, **Duplicate draft**, **Compare drafts**.
6. **Compare view.** Up to 3 drafts in columns, showing per-GW xPts, transfers and chips, with the best per GW highlighted.

**States**
- An "Optimising…" progress state, reusing the agent progress pattern of polling the job.
- "Plan stale: predictions updated", with a re-evaluate button. Re-evaluation is cheap and happens automatically when the view opens.
- Guest: read-only, with a sign-in call to action on edit actions.

**Accessibility.** Every table has a text alternative, ticker colours have a text label (1–5), and the pitch and tables work with the keyboard.

## 6. Data needs (honest)

- **xPts per player per GW for GW+1…GW+8.** Comes from `player_predictions` (sibling spec). Until that ships, the planner can run on the existing heuristic `proj` from `player_metrics`. Today `metrics` computes only the next **6** GWs, so either extend it to 8 or cap the planner at 6. The heuristic can't express hits honestly, so **ship the planner after AI-Transfers P3**, or label projections as "scores" until then.
- **Fixtures for all future GWs.** We have these (`fixtures`). Blank or double GWs only appear once the Premier League reschedules matches. The planner must handle `event IS NULL` fixtures as "unscheduled" and re-evaluate when they move.
- **Squad context.** Bank, FT, selling prices and chips come from `team_snapshots`. Selling prices are *estimated* (ARCHITECTURE §6). The planner inherits that caveat, and the user can override it, as in the existing overrides.
- **Rules.**
  - The FT banking cap: since 2024/25 it is 5 [verify each season; read `game_settings` from bootstrap where present].
  - Squad rules: 2/5/5/3, ≤3 per club, budget.
  - Chip rules: two sets per season with `start_event`/`stop_event`; one chip per GW; FH reverts.
  - Store these in `scoring_rules` / a `game_rules` JSON from the sibling spec's migration, not as constants.
- **Price changes.** We don't predict future price moves; FPL doesn't publish the algorithm. The planner assumes flat prices. Selling price for players bought within the plan = purchase price. This is stated in the UI.

## 7. Algorithms and methodology

### 7.1 Deterministic plan evaluator (`fplcore/planner/evaluate.py`)

Input:
- a snapshot (start state);
- an ordered list of GW actions `{gw, transfers[(out,in)], chip?, xi?, bench?, captain?, vice?}`;
- projections `xpts[p, gw]`.

Steps:

```
state = {squad, bank, ft, purchase_prices, chips_left}
for gw in plan.gws:
    if chip == FH: saved = state.squad (restore after gw)
    for (out, in) in transfers:
        bank += sell_price(out, state)            # snapshot selling price for owned players; = purchase price if bought in-plan
        bank -= now_cost(in); squad = squad − out + in
    n = len(transfers)
    hits = 0 if chip in (WC, FH) else max(0, n − ft)
    validate(squad, bank, club_limits, positions)  → issues[]
    lineup = user lineup or auto_lineup(squad, xpts[·, gw])   # existing lineup.py
    pts = Σ_xi xpts + captain bonus (×1 extra; ×2 extra if TC) + (Σ_bench xpts if BB) − 4·hits
    if chip in (WC, FH): ft = ft                    # FTs retained, none gained, while a WC/FH is active [verify rule each season; driven by the rules table]
    else:                ft = min(ft_cap, ft − min(n, ft) + 1)
    if chip == FH: squad = saved (bank also restored)
    record per-GW {pts, p10, p90, ft_before, ft_after, hits, bank, issues}
total = Σ δ^(gw−gw1) · pts    (δ = 0.85, as in the existing MILP; raw total shown too)
```

- **Cost.** It's pure Python with no solver, and takes under 20 ms for 8 GWs. It runs on every edit, so it's synchronous.
- **Ranges.** Per-GW P10/P90 use a normal approximation from the per-player ranges (assuming independence). This is labelled approximate.
- **Auto-subs** aren't simulated in v1. xPts for starters already include `P(play)`. A later version could add expected auto-sub value from bench order.

### 7.2 Multi-period optimiser (`fplcore/planner/solve.py`, PuLP + CBC)

This extends the existing single-period MILP (ARCHITECTURE §5) to T GWs (T ≤ 8).

**Sets**
- P: candidate players. Pre-filter to the top 40 per position by Σ xPts over T, plus every current, locked or planned player. About 170 players.
- t = 1..T.

**Variables**

| Variable | Type | Meaning |
|---|---|---|
| `x[p,t]` | binary | p is in the squad at the GW t deadline |
| `in[p,t]`, `out[p,t]` | binary | p is transferred in / out at GW t |
| `s[p,t]` | binary | p starts at GW t |
| `c[p,t]` | binary | p is captain at GW t |
| `b[p,t]` | binary | bench-boost contribution |
| `f[t]` | integer ≥ 0 | free transfers used at GW t |
| `h[t]` | integer ≥ 0 | paid hits at GW t |
| `ft[t]` | integer, 0..cap | free transfers available at GW t |
| `bank[t]` | continuous ≥ 0 | money in the bank at GW t |
| `wc[t]`, `fh[t]`, `bb[t]`, `tc[t]` | binary | chip played at GW t |
| `y[p,t]` | binary | Free Hit squad at GW t (separate from `x`) |

**Constraints (main ones)**

| Constraint | Formulation |
|---|---|
| Flow | `x[p,t] = x[p,t−1] + in[p,t] − out[p,t]`, with `x[p,0]` from the snapshot |
| Squad shape | `Σ_p x[p,t] = 15`; position counts 2/5/5/3; `Σ_{p∈club} x[p,t] ≤ 3` |
| Lineup | `s ≤ x` (or `≤ y` when FH); XI = 11 with formation bounds; `c ≤ s`; `Σ c = 1` |
| Budget | `bank[t] = bank[t−1] + Σ sell[p]·out[p,t] − Σ cost[p]·in[p,t]` |
| Transfer count | `Σ in[p,t] = f[t] + h[t] + M·(wc[t] + fh[t])`. The slack is unbounded under a chip, linearised with big-M on h: `h[t] ≥ Σ in[p,t] − f[t] − M·(wc[t]+fh[t])`. |
| FT dynamics | `f[t] ≤ ft[t]`; `ft[t+1] ≤ ft[t] − f[t] + 1 − (wc[t] + fh[t])` (no FT gained in a WC/FH week, per the rules table [verify]); `ft[t+1] ≤ cap`; `ft[t+1] ≥ 1`. The objective never benefits from fewer FTs, so the upper bounds bind. |
| Chips | `Σ_t wc[t] ≤ wc_available_in_half(t)` (per-half sets via `stop_event`); `wc[t] + fh[t] + bb[t] + tc[t] ≤ 1` per GW |
| Free Hit | `y[·,t]` is an independent valid squad under budget `bank[t−1] + value(x[·,t−1])` when `fh[t] = 1`; otherwise `y[p,t] = x[p,t]` (big-M linking). `x[·,t] = x[·,t−1]` across an FH week (no permanent transfers). |
| Bench Boost | `b[p,t] ≤ x[p,t] − s[p,t]` and `b[p,t] ≤ bb[t]` |
| Triple Captain | `tc` adds `xpts·c` again via the auxiliary `ct[p,t] ≤ c[p,t]`, `ct[p,t] ≤ tc[t]` |
| User locks | Fix `x`, `in`, `out` or chip vars. "No hits" sets `h ≡ 0`, "max hits" bounds `Σ h`. |

**Objective**

```
max Σ_t δ^(t−1) · [ Σ_p xpts'[p,t]·(s + c + ct + b) − 4·h[t] ] + ε·Σ_p value_end
```

- `xpts'` is the risk-adjusted xPts from the user's profile (sibling spec §7.3).
- A tiny ε term on end-of-horizon squad value / FT breaks ties toward flexibility.
- A **terminal FT value** (≈ 1.5 xPts per banked FT at t = T, tunable) stops the solver myopically burning transfers at the horizon end.

**Size and speed**
- About 170 players × 8 GWs × 6 binaries ≈ 8k binaries, plus 300 auxiliaries.
- CBC typically solves this in **2–20 s**.
- A Free Hit `y` block roughly doubles the size, so FH placement is only optimised when the user asks or in the chip scan.

**Runtime controls**
- A time limit (default 20 s; paid 45 s) and an MIP gap of 0.5%. Return the best solution found, labelled with the gap.
- Runs **asynchronously** in the existing in-process agent worker. It's a new job kind, so it doesn't block the API.

### 7.3 Chip scan (`fplcore/planner/chips.py`)

- For each available chip k and each GW t in the window (respecting `stop_event`), **evaluate** the user's current draft with chip k at t:
  - BB and TC use the evaluator only (milliseconds).
  - WC and FH re-solve: WC solves multi-period from t with unlimited transfers at t; FH solves a single period at t with unlimited transfers.
- Report the best t, the expected gain against no chip, the runner-up GW and the margin.
- Add a **conflict check**: two chips in the same GW are not allowed. Then suggest a combined schedule with a small enumeration over the top-2 GWs per chip (≤ 16 combos, evaluated in parallel).
- **Agreement with existing rules.** The existing rule thresholds in `agent/chips.py` (BB ≥ 12 bench pts, TC ≥ 10, FH 12, WC 20) remain the agent's quick check. The scan is the planner's precise version. When predictions are on the xPts scale, both should agree on the best GW. **Acceptance test:** they agree in ≥ 80% of backtest cases, and any disagreement is explained.

### 7.4 Re-evaluation on data change

When a new `data_version` lands, a background job re-evaluates every saved draft touched in the last 14 days (evaluator only, cheap). It:
- stores the new totals;
- sets `stale_delta` when the total changes by ≥ 1.0 xPts or a planned player is flagged (status ≠ 'a');
- shows a dashboard banner and an optional chat nudge.

There are no notifications outside the app in v1. Email reminders are a separate future paid item in ARCHITECTURE §2A.

## 8. Data model (SQL DDL additions)

Migration `db/migrations/010_planner.sql`. Needs 009 (`model_versions`, `player_predictions`) from the sibling spec.

```sql
set search_path = fpl, public;

create table plans (
  id            bigserial primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  entry_id      integer not null,
  name          text not null default 'My plan',
  base_snapshot_id bigint not null references team_snapshots(id) on delete cascade,
  start_gw      smallint not null,
  end_gw        smallint not null,
  origin        text not null default 'blank' check (origin in ('blank','agent_fork','duplicate','solver')),
  origin_ref    text,                                  -- e.g. 'agent_run:123/h5' or source plan id
  settings      jsonb not null default '{}',           -- {max_hits, risk_profile, discount, ft_terminal_value}
  revision      integer not null default 1,            -- optimistic concurrency; bumped on every edit
  is_primary    boolean not null default false,
  archived      boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  check (end_gw >= start_gw and end_gw - start_gw < 8)
);
create index plans_user_idx on plans (user_id, entry_id, archived, updated_at desc);
create unique index plans_one_primary on plans (user_id, entry_id) where is_primary and not archived;

-- One row per planned GW (chip, lineup choices, locks).
create table plan_gameweeks (
  plan_id       bigint not null references plans(id) on delete cascade,
  gw            smallint not null,
  chip          text check (chip in ('wildcard','freehit','bboost','3xc')),
  xi            integer[],                             -- null = auto lineup
  bench         integer[],                             -- ordered 4; null = auto
  captain_id    integer,
  vice_id       integer,
  locks         jsonb not null default '{}',           -- {"keep":[..],"exclude":[..],"no_hits":true,"chip_fixed":true}
  primary key (plan_id, gw)
);

-- Ordered transfers within a GW.
create table plan_transfers (
  plan_id       bigint not null references plans(id) on delete cascade,
  gw            smallint not null,
  seq           smallint not null,
  out_player_id integer not null,
  in_player_id  integer not null,
  source        text not null default 'user' check (source in ('user','solver','agent')),
  locked        boolean not null default false,        -- solver must keep it
  primary key (plan_id, gw, seq),
  foreign key (plan_id, gw) references plan_gameweeks(plan_id, gw) on delete cascade,
  check (out_player_id <> in_player_id)
);

-- Cached evaluation of a plan revision against a data/model version.
create table plan_evaluations (
  plan_id       bigint not null references plans(id) on delete cascade,
  revision      integer not null,
  data_version  bigint not null references data_versions(id),
  model_version text references model_versions(id),
  total_xpts    numeric(7,2) not null,                 -- discounted
  total_xpts_raw numeric(7,2) not null,
  per_gw        jsonb not null,                        -- [{gw, pts, p10, p90, ft_before, ft_after, hits, bank, chip, issues[], reason_codes[]}]
  baseline_xpts numeric(7,2),                          -- "do nothing" over the same window
  stale_delta   numeric(6,2),                          -- change vs the previous evaluation, if any
  computed_at   timestamptz not null default now(),
  primary key (plan_id, revision, data_version)
);

-- Async solver / chip-scan jobs (same claim pattern as agent_runs: FOR UPDATE SKIP LOCKED).
create table planner_jobs (
  id            bigserial primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  plan_id       bigint not null references plans(id) on delete cascade,
  plan_revision integer not null,
  kind          text not null check (kind in ('solve','chip_scan')),
  params        jsonb not null,                        -- {gw_from, gw_to, time_limit_s, mip_gap, chips_allowed, ...}
  status        text not null default 'queued' check (status in ('queued','running','succeeded','failed','cancelled')),
  progress      smallint not null default 0 check (progress between 0 and 100),
  result        jsonb,                                 -- proposed actions (not auto-applied) + objective + gap
  error         text,
  attempts      smallint not null default 0,
  locked_by     text,
  created_at    timestamptz not null default now(),
  started_at    timestamptz,
  finished_at   timestamptz
);
create index planner_jobs_queue_idx on planner_jobs (created_at) where status = 'queued';
create unique index planner_jobs_one_active on planner_jobs (user_id) where status in ('queued','running');

-- RLS: API connects as owner and enforces user_id = JWT sub; policies are defence in depth (same as agent tables).
alter table plans            enable row level security;
alter table plan_gameweeks   enable row level security;
alter table plan_transfers   enable row level security;
alter table plan_evaluations enable row level security;
alter table planner_jobs     enable row level security;

create policy "plans: read own" on plans
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "plan_gameweeks: read own" on plan_gameweeks
  for select to authenticated using (exists (select 1 from plans p where p.id = plan_id and p.user_id = (select auth.uid())));
create policy "plan_transfers: read own" on plan_transfers
  for select to authenticated using (exists (select 1 from plans p where p.id = plan_id and p.user_id = (select auth.uid())));
create policy "plan_evaluations: read own" on plan_evaluations
  for select to authenticated using (exists (select 1 from plans p where p.id = plan_id and p.user_id = (select auth.uid())));
create policy "planner_jobs: read own" on planner_jobs
  for select to authenticated using ((select auth.uid()) = user_id);
```

**Design notes**
- Solver results land in `planner_jobs.result` as a *proposal*. Applying one is an explicit user action that writes `plan_transfers` with `source='solver'` and bumps `revision`. The solver never silently overwrites user edits.
- **Limits:** free = 1 active (non-archived) plan per entry; paid = 10. These are enforced in the API, the same way `tracked_entries` is.
- **Retention:** archived plans are deleted after 60 days. `plan_evaluations` keeps the latest 5 per plan.
- Guest read-only planner state lives in the browser only (no DB rows), in keeping with the "guests never create snapshots" rule.

## 9. API endpoints

| Method & path | Auth | Description |
|---|---|---|
| `GET /fixtures/ticker?from=&to=&teams=` | Public | Per team, per GW: opponents, home/away, FDR, model difficulty (from `team_strengths`), DGW/BGW flags. Cached per `data_version`. |
| `GET /public/plan-preview/{entry_id}?gws=3` | Public | Guest read-only: the holding squad's per-GW xPts and ticker. Uses `entry_cache`; nothing stored. Per-IP limit. |
| `GET /me/plans` | User | The user's plans: id, name, totals and stale flag. |
| `POST /me/plans` `{name?, from: 'blank'\|'agent'\|'plan', agent_run_id?, horizon?, source_plan_id?, gws?}` | User | Create a plan from the latest snapshot, a fork of an agent horizon plan, or a duplicate. Enforces tier limits. |
| `GET /me/plans/{id}` | User | Full plan, plus the latest evaluation (re-evaluated synchronously if stale). |
| `PATCH /me/plans/{id}` `{revision, name?, settings?, is_primary?, archived?}` | User | Metadata. Returns 409 on a revision mismatch. |
| `PUT /me/plans/{id}/gw/{gw}` `{revision, transfers[], chip?, xi?, bench?, captain_id?, vice_id?, locks?}` | User | Replace one GW's actions. Returns the new revision and evaluation (synchronous, < 300 ms). |
| `POST /me/plans/{id}/evaluate` `{what_if?: {gw, transfers?, chip?}}` | User | Evaluate the plan or an unsaved what-if without saving it. Used by the UI and the chat tool. |
| `POST /me/plans/{id}/solve` `{gw_from, gw_to, max_hits?, chips_allowed?, time_limit_s?}` | User | Queue a `planner_jobs` solve. Returns `job_id`. Free: 1/hour, T ≤ 5. Paid: 10/hour, T ≤ 8. |
| `POST /me/plans/{id}/chip-scan` | User | Queue a chip scan. Returns `job_id`. |
| `GET /me/planner-jobs/{job_id}` | User | `{status, progress, result?}`. Returns 404 unless the job is the caller's. |
| `POST /me/plans/{id}/apply/{job_id}` `{revision}` | User | Apply a solver proposal. Returns the new revision. |
| `GET /me/plans/compare?ids=1,2,3` | User | Side-by-side per-GW totals. |

**Shared conventions**
- Pydantic models; slowapi per-`sub` limits (`PLANNER_SOLVE_LIMIT_PER_HOUR`).
- The worker claims `planner_jobs` the same way as `agent_runs`, with the same stale-run recovery.
- New env vars: `PLANNER_MAX_GWS`, `PLANNER_SOLVE_TIME_LIMIT_S`, `PLANNER_MIP_GAP`, `PLANNER_FT_TERMINAL_VALUE`.

**Chat harness additions** (CHATBOT_HARNESS_SPEC §6.3)
- `get_plan(plan_id?)` returns a compact per-GW summary.
- `evaluate_plan_change(plan_id, what_if)` returns a delta versus the current plan. It's read-only: chat never saves edits without the user pressing a confirm button in the UI.
- Both are signed-in only, and both count toward existing chat tool-call caps.

## 10. Tier placement

| Capability | Guest | Free (signed in) | Future paid |
|---|---|---|---|
| Fixture ticker (FDR and model difficulty) | ✅ | ✅ | ✅ |
| Planner view of the holding squad | ✅ 3 GWs, read-only | ✅ | ✅ |
| Manual drafts (transfers, chips, lineup) | – | ✅ 1 draft, 5 GWs | ✅ 10 drafts, 8 GWs, compare 3 |
| Fork the agent plan into a draft | – | ✅ | ✅ |
| Multi-period solver | – | ✅ 1 run/hour, T ≤ 5, 20 s limit | ✅ 10/hour, T ≤ 8, 45 s, FH optimisation |
| Chip scan | – | Rule-based advice (existing agent) | ✅ full scan with combined schedule |
| Stale-plan alerts | – | In-app banner | In-app plus email (future reminders feature) |
| Chat what-ifs on the plan | – | Within free chat caps | Higher caps |

**Rationale.**
- A basic planner is free elsewhere (fpl.team, FPL Review's free planner), so manual planning must be free to compete.
- Paid value is the solver depth, chip intelligence and multiple scenarios. ARCHITECTURE §2A already reserves a "multi-GW chip planner" and multiple teams for paid.

## 11. Dependencies

- **`FEATURE_SPEC_AI_TRANSFERS`:**
  - P2 (`player_predictions` for GW+1..+8, `team_strengths` for the ticker);
  - P3 (re-tuned hit and chip margins on the xPts scale).
  - Fallback: run on the heuristic `proj`, capped at 6 GWs, labelled "scores".
- **Existing code:**
  - `fplcore.optimise` (constraint helpers to reuse; new `planner/solve.py`);
  - `lineup.py` (auto XI and bench);
  - `agent/chips.py` (rule thresholds);
  - the `agent/runner.py` worker loop (add a `planner_jobs` claimer);
  - team snapshot and FT/selling-price estimation (ARCHITECTURE §6);
  - the `api/services.py` patterns.
- **Ingest:** extend the `metrics`/`predictions` window to 8 GWs, and keep fixture changes flowing (DGW/BGW announcements).
- **Front end:**
  - a pitch component reused per GW;
  - drag-and-drop for chips (keyboard accessible);
  - polling hook (reuse the agent progress hook).
- **Infra:** a CBC solve of up to 45 s on the API host's worker thread. Check CPU and memory on the Render/Fly free tier [verify]. If it's too slow, move solves to a GitHub Actions or dedicated worker queue later. The `planner_jobs` table is already queue-shaped.

## 12. Phased milestones and acceptance criteria

| Phase | Scope | Acceptance criteria |
|---|---|---|
| **PL0 Ticker** (3–4 days) | `GET /fixtures/ticker`, ticker UI (dashboard and guest) | Correct DGW/BGW display for a GW with a known postponement. Model difficulty matches `team_strengths`. Loads in < 300 ms (cached). |
| **PL1 Evaluator + read-only planner** (1 wk) | `planner/evaluate.py`, guest `/public/plan-preview`, dashboard view of the holding squad | Unit tests reproduce FT banking to the cap, hits, WC/FH free transfers, FH reversion, BB/TC scoring, and selling prices. Evaluator totals for a "no transfers" plan equal Σ auto-lineup xPts. < 20 ms per 8-GW evaluation. |
| **PL2 Drafts** (1–1.5 wks) | Migration 010; CRUD endpoints; per-GW editing UI; validation; fork agent plan; revision/409 handling; tier limits | A user can create, edit and reload a 5-GW draft. Invalid states (budget, club limit, formation) are flagged with a specific message. A concurrent edit returns 409 and the UI recovers. A forked agent plan's GW1 transfers exactly match the agent's plan. |
| **PL3 Solver** (1.5–2 wks) | `planner/solve.py` multi-period MILP; `planner_jobs` worker; proposal/apply flow | Property tests on 200 random squads: every solution is valid every GW, respects locks, and has ≥ the evaluator total of "do nothing" and of the 1-period agent plan held over T. 95% of T=5 solves finish in < 20 s with gap ≤ 0.5% on the target host. |
| **PL4 Chip scan** (1 wk) | `planner/chips.py`, combined schedule, expiry warnings | On backtest seasons, the best-GW picks agree with a brute-force evaluator in 100% of BB/TC cases. Agreement with the agent's rule-based advice is ≥ 80%, and disagreements are explained. |
| **PL5 Re-evaluation, compare, chat** (1 wk) | Stale detection job, banner, compare view, `get_plan` / `evaluate_plan_change` chat tools | After an injury flag on a planned player, the user's draft shows a stale banner within one ingest cycle. Chat what-ifs return the same numbers as `/evaluate`. |
| **PL6 Paid depth** (after the billing decision) | 8 GWs, 10 drafts, longer solves, FH optimisation | Limits are enforced server-side with clear upgrade messaging. Free behaviour is unchanged. |

## 13. Risks and open questions

**Risks**
- **Solver runtime on free-tier hosting.** Mitigation: pre-filter candidates, time limits, MIP gap, async jobs, and FH optimisation only on request. The `planner_jobs` queue can move to a separate worker.
- **Selling-price and FT estimates may be wrong** (FPL's private "my team" endpoint isn't used). Mitigation: show the assumptions, allow overrides (existing pattern), and recompute from the next import.
- **Unscheduled fixtures make far-future GWs uncertain.** Mitigation: mark GWs with pending rescheduling. A "possible DGW" note can come from fixtures with `event IS NULL`. Don't invent probabilities in v1.
- **False precision across 8 GWs.** Mitigation: show ranges, discount future GWs (δ), and default the planner window to 5 GWs.
- **Rule changes** (FT cap, chip sets, special mid-season transfer top-ups like those FPL has run before). Mitigation: rules live in data, not code, with a pre-season checklist.
- **UX complexity on mobile.** Mitigation: on mobile, show a single-GW pitch with swipe between GWs, and the timeline as a compact strip.
- **Overlap with the agent.** Users may be confused about whether to follow the agent or their plan. Mitigation: the agent's N=3/5 plan *is* a forkable draft, and the planner's summary always shows "vs Agent plan".

**Open questions**
1. Should a saved primary plan feed back into the agent, e.g. "keep my GW12 move", as locks for the agent's N=1/3/5 runs? Proposed: yes, as soft locks in a later phase.
2. Model expected price changes? Proposed: no in v1, given the accuracy risk (users already complain about rivals' price predictions; R1).
3. Should the discount δ (0.85) and terminal FT value be user-visible settings, or fixed?
4. Should the free tier get 1 draft or 2? The evidence suggests basic planning must be free to compete with fpl.team and FPL Review.
5. The planner name in the UI, e.g. "Planner" or "Season Plan". Avoid rival naming.
