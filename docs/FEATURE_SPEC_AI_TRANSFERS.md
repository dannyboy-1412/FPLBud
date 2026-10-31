# Feature spec: AI Transfers with Predicted Points (xPts engine, team rating, transfer picks)

*Draft 1, 31 Oct 2026 (Sydney). Status: proposal. Owner: Daniel.*

**Related documents**
- Rival evidence: [`RIVAL_ANALYSIS_FFHUB.md`](RIVAL_ANALYSIS_FFHUB.md), §3–4.1.
- Builds on: `docs/ARCHITECTURE.md` §5 (MILP), §6A (team agent), §2A (tiers); `db/schema.sql`; [`CHATBOT_HARNESS_SPEC.md`](CHATBOT_HARNESS_SPEC.md) §6 (tools).
- Sibling: [`FEATURE_SPEC_TEAM_PLANNER.md`](FEATURE_SPEC_TEAM_PLANNER.md), which consumes this feature's predictions.

---

## 1. Problem and user value

FPL managers have two questions every week: **"How many points will each player score?"** and **"Given my squad, bank and free transfers, what should I do?"**

Fantasy Football Hub's main selling point is a points model plus personalised AI transfers. It was mentioned in 11/14 and 8/14 user sources respectively (rival analysis §3.2). Those same users complain that:
- the predictions are inaccurate and feel stale;
- the AI is a black box;
- a "98/100" rating told them nothing.

FPLBud already answers the second question with an explainable optimiser. The weak link is the first question. Today, `proj` is a **heuristic**: the combined 0..1 metric score `S` is mapped to points with a fallback `a·S + b` (ARCHITECTURE §5; `fplcore.metrics.projected_points`). It isn't calibrated in points, so:
- hit maths (−4) and captain margins are only roughly right;
- we can't publish a "predicted points" number we can defend.

**User value of this feature**
1. **A real predicted-points number (xPts) per player per GW**, made of FPL scoring components (minutes, goals, assists, clean sheets, saves, bonus, defensive contributions). It comes with a range and published accuracy.
2. **Better transfer picks** from the existing MILP and agent, now optimising calibrated points. That makes "is this −4 worth it?" a real calculation.
3. **A team rating that means something.** It is defined as "% of the points an optimal squad of your value would get", and it lists the specific leaks and fixes.
4. **Trust.** A public accuracy page compares us with FPL's own `ep_next` every gameweek. No rival in the evidence does this.

## 2. What the rival does (cited)

**Tiering**
- Starter (cheapest paid tier, ≈ A$62/yr at the current 50% discount; see rival analysis §2) includes "Recommended AI transfers", "Team Rated by AI" and "My Team Predicted Points". Source: [/join](https://www.fantasyfootballhub.co.uk/join) table, rendered 31 Oct 2026.
- The "Predicted Points Tool" for all players is Pro-only. Source: [Freshdesk tiers article](https://fantasyfootballhub.freshdesk.com/support/solutions/articles/103000113576-what-are-the-differences-between-tiers-).

**Free funnel**
- The free AI Team Rating "scores your squad in seconds and shows exactly where it's leaking points". It requires an email. Then "AI Transfers picks the best move for your team". Source: [homepage](https://www.fantasyfootballhub.co.uk/) FAQ.

**How the AI is described**
- "AI Recommended Transfers based on our proprietary prediction models", "Customisable AI Suggestions tailored to your exact team scenario, budget, and strategy". Source: [Google Play listing](https://play.google.com/store/apps/details?id=uk.co.fantasyfootballhub.app).
- The method is not published. I found no public accuracy figures from FFH.
- The money-back promise requires users to "follow the AI's recommendations". Source: [landing page](https://www.fantasyfootballhub.co.uk/landing/LTFPL).

**User reception**
- Praise: "AI transfers and predicted points section were instrumental" (Trustpilot T1).
- Criticism:
  - "points predicting… so off the mark" (T4);
  - "rated 98/100… below average" (Reddit R1);
  - AI transfers said no moves for 5 GWs (R1);
  - "The expected points metric can be used as a good baseline" but not followed blindly (R1).

## 3. FPLBud approach and differentiation

| | FFH (as observed) | FPLBud |
|---|---|---|
| Points model | Proprietary, unexplained, licensed OPTA data | **Component xPts model** built from FPL's public per-match data (xG, xA, minutes, DC, BPS) and team strengths. Method published on `/how-it-works`. |
| Accuracy | Not published | **Public `/accuracy` page**: MAE, RMSE, rank correlation and calibration per GW and position, versus `ep_next` and versus our old heuristic. Walk-forward backtest on past seasons. |
| Uncertainty | Single number | **P10–P90 range** per player per GW. Hit and captain decisions show "gain ± spread". |
| Transfers | AI picks, some customisation | Existing **PuLP MILP** (lock, exclude, max hits, roll vs 1/2/n transfers), now on calibrated xPts. Every pick shows **why**: the component deltas (e.g. "+0.6 xG/90, easier fixtures, 92% start probability"). |
| "No transfers" advice | Unexplained | Always shows the **roll alternative** and the margin a move missed by, plus a "force best 1 transfer" button. |
| Personalisation | "Customisable suggestions" | Keep users' **metric weights** as an optional *tilt* on top of xPts (§7.5), plus risk appetite (safe vs upside, from the P10/P90 range). |
| Rating | 0–100, opaque | **Squad Efficiency %** = your best-XI xPts ÷ the optimum xPts for your squad value over 1/3/5 GWs, with the top 3 leaks and fixes. |
| Paywall | All paid except the rating | Guests: next-GW xPts table, rating and a 1-GW plan with **no email wall**. Paid adds depth (§10). |

## 4. User stories

**Guest**
1. As a guest, I can enter my team ID and see my **Squad Efficiency** with the three biggest leaks, without an email.
2. As a guest, I can browse **next-GW xPts** for every player, filtered by position, team and price.

**Signed-in user**
3. As a signed-in user, my 1/3/5-GW agent plans use xPts. Each transfer card shows the xPts gain, its range, and the components that drove it.
4. As a user, when the agent says "roll", I see how close the best move came. I can force "best single transfer" or "best with one −4".
5. As a user, I can open a player and see their per-GW xPts breakdown (minutes, attack, defence, bonus, DC) next to their last 6 actual GWs.
6. As a user, I can choose **projection mode** (Model, or Model + my metric tilt) and **risk** (safe / balanced / upside).
7. As a user, I can ask the chatbot "why is X predicted 6.1?" and get an answer grounded in the breakdown.

**Anyone**
8. As anyone, I can open `/accuracy` and see how well last GW's predictions did.

**Maintainer**
9. As Daniel (maintainer), I can backtest a new model version on past seasons, compare it with the active one, and promote it with one flag.

## 5. UX and pages

**Changes to existing pages**
- **`/try/[entryId]` (guest).** Add a **Squad Efficiency card** above the pitch: big %, a "best XI xPts vs optimum" bar, and the 3 leaks (player → suggested fix, +xPts). The existing next-GW plan card gains xPts numbers. The Next 3 / Next 5 tabs stay blurred, with sign-in to unlock.
- **`/dashboard?section=plans`.**
  - Transfer cards show `+2.4 xPts (range −0.8…+5.1)`, with component chips (Minutes ↑, xG ↑, Fixtures ↑, DC ↑) and a "Why?" expander.
  - A "Roll" card shows "best move was +1.1, below the +2.0 threshold for N=1".
  - Buttons: **Force 1 transfer** and **Allow 1 hit**. These call `POST /suggestions` with overrides.

**New pages and sections**
- **`/predictions`** (public). A sortable table: player, team, position, price, ownership, xPts for GW+1…GW+6 (sum and per GW), start %, range. Filters for position, team and max price. Guests see GW+1 to GW+3. Signed-in users see up to GW+6 (paid: GW+8 and CSV export).
- **Player drawer** (existing `player_detail`). Adds a stacked bar of the xPts components per GW, and "last 6 GWs: predicted vs actual".
- **`/accuracy`** (public).
  - Last GW: MAE overall and by position, and versus `ep_next`.
  - Season-to-date chart.
  - Calibration plot (predicted bucket vs mean actual).
  - Model version and changelog.
- **`/settings`.** Add a projection mode (Model / Model + my tilt) and a risk profile.
- **`/how-it-works`.** Add an "xPts model" section in plain English. No proprietary rival content.

## 6. Data: what we have, what we need, how to get it

**Available today**

| Need | Have today? | Source / plan |
|---|---|---|
| Per-match player rows (minutes, starts, xG, xA, xGC, DC, BPS, bonus, saves, points) | Yes, but only a **rolling window** of about 8 GWs (`player_gameweek_stats`, pruned) | Stop deleting: move pruned rows into `player_match_archive` (§8) |
| Current-season per-player history | Yes, from `element-summary/{id}` `history` (all GWs this season) | Already fetched by the `element_summaries` ingest |
| Past seasons, per match | **No.** FPL's API only gives season totals (`history_past`) | **Backfill from [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)**: `data/<season>/gws/merged_gw.csv`, 2016-17 → 2026-27. It includes `xP` (FPL's own expected points, as a baseline), and `expected_goals` / `expected_assists` from 2022-23 onwards. |
| Team attack/defence strength | Partial. `teams.strength_*` are coarse, and `strength_attack_*` is currently 0 | **Fit our own** from fixtures: team xG for/against per match = sum of players' xG/xGC in `player_gameweek_stats` |
| Set-piece / penalty order | Yes (`players.penalties_order`, etc.) | Current only; no history |
| Scoring rules | Implicit | New `scoring_rules` table per season, checked against the official FPL rules each pre-season. Rules changed in 2025/26: defensive contribution points were added. |
| OPTA event data | **No** (licensed; FFH pays for it) | Out of scope. Use FPL's xG/xA/DC, which FPL itself sources from Opta. |

**Licensing and terms (must verify before launch)**
- The vaastav repo's code is MIT. Its README states the data "is property of fantasy.premierleague.com and understat.com".
- Treat the dataset as **internal training data only**. Don't redistribute raw CSVs.
- Check the FPL terms of use before publicly re-displaying historical per-match data. Our own derived predictions and accuracy statistics are fine to show.
- Keep a `data_sources` note in the repo.

**Volume**
- About 25k player-match rows per season, times 4 seasons with xG (2022-23 → 2025-26). That's about 100k rows, trivial for Postgres and for local training.
- Training runs **offline**, in GitHub Actions or locally (`scripts/`), not on the API box.

## 7. Algorithms and methodology

### 7.1 xPts as a sum of scoring components (per player p, fixture f)

All parameters are fitted by position, on past seasons, with walk-forward validation.

```
xPts(p,f) = Appearance(p,f) + Attack(p,f) + Defence(p,f) + Saves(p,f) + DC(p,f) + Bonus(p,f) − Cards/OG(p,f)
```

**Minutes model**
- Estimate `P(start)` and `P(sub appearance)` from the last 3/6/10 matches' starts and minutes (exponentially weighted), `status`, `chance_of_playing_next_round` and `news` flags.
- Add a fixture-congestion term: days since the last match, from `fixtures.kickoff_time`.
- Derive `E[min]`, `P(min ≥ 60)` and `P(1 ≤ min < 60)`.
- Model: logistic regression for `P(start)`; empirical minutes distribution given start or bench, by position.
- `Appearance` = `P(1..59)·1 + P(≥60)·2` (points from `scoring_rules`).

**Attack**
- Per-90 rates for non-penalty xG and xA are shrunk toward a position prior (empirical Bayes), using a recency-weighted blend of this season and last season.
  - The shrinkage strength is fitted. This fixes "feels like last year's stats" by making the recency weight explicit and tuned.
- Then scale by an opponent and venue adjustment from team strengths (§7.2).
- Penalty takers (`penalties_order = 1`) get `+ team_pen_rate × 0.76 xG`. The conversion constant should be fitted.
- `λ_goals = rate_xg × adj × E[min]/90`, and `λ_assists` likewise.
- `Attack = goal_pts[pos] × λ_goals + assist_pts × λ_assists`. Poisson expectations are linear, so the expected points are exact.

**Defence (GK/DEF full, MID partial)**
- `λ_conc` = the opponent's attack × our team's defence × venue (§7.2).
- `CS = cs_pts[pos] × P(≥60) × e^(−λ_conc)`.
- The goals-conceded penalty uses the Poisson expectation of ⌊goals/2⌋ while on the pitch, scaled by minutes share.

**Saves (GK)**
- Expected saves from the opponent's shot volume proxy. That is λ_conc × a fitted saves-per-goal-conceded ratio, divided by 3, times save points.

**Defensive contribution**
- `P(DC threshold reached)` is a logistic of the player's recent DC per 90 and their minutes. It uses `defensive_contribution` per match from `player_gameweek_stats`, which only exists from 2025/26.
- Two seasons of history at most, so this is flagged lower-confidence.

**Bonus**
- Regress realised bonus on predicted component points and position (an ordinal or Poisson GLM). Simple and honest. A BPS simulation is a later option.

**Cards and own goals**
- Small per-player rates, shrunk toward the position mean.

**Gameweek totals**
- Double GWs sum their fixtures. Blank GWs are 0.
- Multiply by availability for gameweeks beyond next (existing `availability()` decay, k ≥ 2).

### 7.2 Team strengths

- Fit a **Poisson model on team xG**:
  - `xG_for(home h vs a) ~ exp(μ + att_h − def_a + home)`, from per-fixture sums of players' xG (we have these in `player_gameweek_stats`; the archive covers past seasons).
  - Weighting is time-decayed (half-life about 15 matches, tuned), with a carry-over prior from last season shrunk toward the mean. The prior covers promoted teams and early-season noise.
- This replaces the coarse FDR in the model. The existing `fixture_score` metric stays for the "my metrics" tilt and the fixture ticker.
- Fitted nightly. A small regularised GLM fits in under 1 s with `statsmodels` or `scipy`.

### 7.3 Uncertainty (P10/P90)

- Monte Carlo per player-GW (1,000 draws, vectorised NumPy):
  - minutes bucket ~ the minutes model;
  - goals and assists ~ Poisson(λ);
  - conceded ~ Poisson(λ_conc);
  - bonus ~ the fitted distribution.
- Store P10, P50 and P90.
- Cost: about 700 players × 8 GWs × 1,000 draws ≈ 5.6M draws, a few seconds in the nightly job.
- In the optimiser, **risk mode** swaps the objective: safe = mean − 0.25·(P50−P10), upside = mean + 0.25·(P90−P50). The constants are tunable.

### 7.4 Validation (gate before any model is promoted)

- **Walk-forward backtest.** For each GW g in the 2023-24 → 2025-26 seasons, train on data available before g's deadline only, then predict GW g … g+5.
- Metrics, overall and by position, for players with ≥1 minute and for all owned/selectable players:
  - MAE and RMSE;
  - Spearman rank correlation within position (what matters for picking);
  - calibration (10 buckets);
  - top-k hit rate (are the model's top 20 the actual top 20?).
- **Baselines**, all of which must be reported:
  1. FPL `ep_next` / historical `xP`;
  2. the current heuristic `a·S+b`;
  3. a naive "points per game, last 5".
- **Promotion gate**
  - **v1 must beat (2) on every metric**, and match or beat (1) on Spearman, on 2 of 3 held-out seasons.
  - If it doesn't beat `ep_next`, ship it anyway as an *explainable* model, but **say so on `/accuracy`**. Honesty is the differentiator.
- **Decision backtest.** Run the existing agent (`scripts/backtest.py`, ARCHITECTURE M8) with the old projection and with xPts over a past season, from a fixed template squad. Compare realised points of the recommended moves. This also re-tunes the hit margins in `HORIZON_SETTINGS`.

### 7.5 Using xPts in the optimiser and agent

- **Integration point.** In `api/services.py:load_opt_players`, `rec["proj"][gw]` currently comes from `projected_points(score=combined_score(scores, weights), …)`.
- **New logic**
  ```
  base = xpts(p, gw)                                   # from player_predictions (active model)
  if mode == 'model':  proj = base
  if mode == 'tilt':   proj = base × (1 + τ × (S_user(p,gw) − S_default(p,gw)))   # τ = 0.3, clipped ±30%
  ```
  - This keeps custom weights meaningful: they tilt the projection toward the user's beliefs instead of replacing a calibrated number.
  - Guests always get `model`.
- **Fallback.** If there's no prediction row (new player, missing fit), fall back to the existing heuristic and flag `PROJ_FALLBACK` in `reason_codes`.
- `HORIZON_SETTINGS` (1/3/5), the hit margins and the chip thresholds (BB 12, TC 10, FH 12, WC 20) now operate on real points. **Re-tune them with the decision backtest.** The thresholds were chosen for the heuristic scale.
- **New `reason_codes`:** `XPTS_MINUTES_UP`, `XPTS_ATTACK_UP`, `XPTS_DEFENCE_UP`, `XPTS_DC_UP`, `NEAR_MISS_ROLL` (best move within 25% of the threshold), and `HIGH_VARIANCE_PICK`.
- **Explanations.** The `TemplateExplainer` gets component deltas. The `LLMExplainer` (paid) gets the same JSON, and the existing grounding check still applies.

### 7.6 Squad Efficiency (team rating)

```
For horizon N (1 for guests; 1/3/5 for users):
  mine = Σ_gw δ^(gw−1) · (best XI xPts + captain bonus) for the current squad, no transfers
  opt  = the same for the MILP-optimal 15 under the same total budget (team value + bank, using selling prices), unlimited transfers
  efficiency = 100 × mine / opt     (shown as "84% of optimum")
  leaks = top 3 by (best affordable replacement's xPts − player's xPts) over N, with the swap
```

- **Cost:** one extra MILP solve (wildcard mode, already supported via `unlimited_transfers=True`), about 100–300 ms. It's cached per `(entry_id, event, squad_hash, model_version, N)`.
- **Honesty.** Show "≈ ±X%" from the P10/P90 spread. Don't show a meaningless 98/100. Optimum is the denominator, so a perfect score is genuinely rare.

## 8. Data model (SQL DDL additions)

Migration `db/migrations/009_predictions.sql`, numbered after the chat harness's 008. Tables are in the `fpl` schema via `search_path`, like the rest.

```sql
set search_path = fpl, public;

-- Versioned models; exactly one active.
create table model_versions (
  id            text primary key,                 -- e.g. 'xpts-2026.11.1'
  description   text not null,
  trained_through date not null,                  -- last match date used for fitting
  params        jsonb not null,                   -- shrinkage, half-lives, coefficients, scoring_rules version
  backtest      jsonb,                            -- summary metrics from §7.4
  is_active     boolean not null default false,
  created_at    timestamptz not null default now()
);
create unique index model_versions_one_active on model_versions (is_active) where is_active;

-- FPL scoring rules per season (verified each pre-season against the official rules).
create table scoring_rules (
  season_id     text not null references seasons(id),
  position_id   smallint not null references positions(id),
  rules         jsonb not null,                   -- {"goal":..,"assist":..,"cs":..,"gc_per_2":..,"dc_threshold":..,"dc_pts":..,...}
  verified_at   date,
  primary key (season_id, position_id)
);

-- Long-term per-match history (current-season rows moved here instead of being pruned, plus the past-season backfill).
-- Keyed by players.code (stable across seasons), because element ids change each season.
create table player_match_archive (
  season_id     text not null,
  player_code   integer not null,
  fixture_id    integer not null,
  round         smallint not null,
  team_code     integer,
  opponent_team_code integer,
  was_home      boolean not null,
  position_id   smallint not null references positions(id),
  minutes       smallint not null,
  starts        smallint,                         -- null for seasons before FPL exposed it
  total_points  smallint not null,
  goals_scored  smallint not null,
  assists       smallint not null,
  clean_sheets  smallint not null,
  goals_conceded smallint not null,
  saves         smallint not null,
  bonus         smallint not null,
  bps           smallint not null,
  yellow_cards  smallint not null default 0,
  red_cards     smallint not null default 0,
  own_goals     smallint not null default 0,
  defensive_contribution smallint,                -- null before 2025/26
  expected_goals numeric(5,2),                    -- null before 2022/23
  expected_assists numeric(5,2),
  expected_goals_conceded numeric(5,2),
  fpl_xp        numeric(4,1),                     -- FPL's own expected points at the time (baseline)
  value         smallint not null,
  source        text not null check (source in ('fpl_api','vaastav')),
  primary key (season_id, player_code, fixture_id)
);
create index pma_season_round_idx on player_match_archive (season_id, round);

-- Fitted team strengths per target GW.
create table team_strengths (
  season_id     text not null,
  team_id       smallint not null,
  gw            smallint not null,
  model_version text not null references model_versions(id),
  attack        numeric(6,4) not null,
  defence       numeric(6,4) not null,
  home_adv      numeric(6,4) not null,
  computed_at   timestamptz not null default now(),
  primary key (season_id, team_id, gw, model_version),
  foreign key (season_id, team_id) references teams(season_id, id)
);

-- Per-player per-GW predictions (GW total; DGWs summed, blanks = 0 rows written with fixture_count 0).
create table player_predictions (
  season_id     text not null,
  player_id     integer not null,
  gw            smallint not null,
  model_version text not null references model_versions(id),
  data_version  bigint references data_versions(id),
  fixture_count smallint not null,
  p_start       numeric(4,3) not null,
  xmins         numeric(5,2) not null,
  p60           numeric(4,3) not null,
  xg            numeric(5,3) not null,
  xa            numeric(5,3) not null,
  p_cs          numeric(4,3) not null,
  pts_appearance numeric(5,2) not null,
  pts_attack    numeric(5,2) not null,
  pts_defence   numeric(5,2) not null,            -- CS + GC penalty
  pts_saves     numeric(5,2) not null default 0,
  pts_dc        numeric(5,2) not null default 0,
  pts_bonus     numeric(5,2) not null default 0,
  pts_other     numeric(5,2) not null default 0,  -- cards, OG, pen misses
  xpts          numeric(5,2) not null,
  xpts_p10      numeric(5,2) not null,
  xpts_p50      numeric(5,2) not null,
  xpts_p90      numeric(5,2) not null,
  computed_at   timestamptz not null default now(),
  primary key (season_id, player_id, gw, model_version),
  foreign key (season_id, player_id) references players(season_id, id)
);
create index pp_gw_idx on player_predictions (season_id, gw, model_version);

-- Accuracy tracking: written after each GW finishes (and by the backtest for past seasons).
create table prediction_evaluations (
  model_version text not null references model_versions(id),
  season_id     text not null,
  gw            smallint not null,
  lead          smallint not null default 1,      -- predicted 1..6 GWs ahead
  position_id   smallint not null default 0,      -- 0 = all positions
  n             integer not null,
  mae           numeric(6,3) not null,
  rmse          numeric(6,3) not null,
  spearman      numeric(5,4),
  bias          numeric(6,3),
  mae_ep_next   numeric(6,3),                     -- baseline on the same rows
  mae_heuristic numeric(6,3),
  calibration   jsonb,                            -- [{bucket_lo, bucket_hi, mean_pred, mean_actual, n}]
  is_backtest   boolean not null default false,
  computed_at   timestamptz not null default now(),
  primary key (model_version, season_id, gw, lead, position_id)
);

-- Squad Efficiency cache (public data only; no user id, like entry_cache).
create table team_ratings (
  entry_id      integer not null,
  event         smallint not null,
  squad_hash    text not null,
  model_version text not null references model_versions(id),
  horizon       smallint not null check (horizon in (1,3,5)),
  efficiency    numeric(5,2) not null,            -- 0..100
  my_xpts       numeric(6,2) not null,
  opt_xpts      numeric(6,2) not null,
  spread        numeric(5,2),                     -- ± percentage points
  leaks         jsonb not null,                   -- [{out, in, gain, reason_codes}]
  created_at    timestamptz not null default now(),
  primary key (entry_id, event, squad_hash, model_version, horizon)
);

-- Agent results record which model produced them.
alter table agent_suggestions add column model_version text references model_versions(id);

-- User preferences.
alter table public.profiles
  add column projection_mode text not null default 'model' check (projection_mode in ('model','tilt')),
  add column risk_profile    text not null default 'balanced' check (risk_profile in ('safe','balanced','upside'));

-- Public read-only data: keep closed to anon/authenticated (API reads as owner), consistent with existing tables.
alter table model_versions          enable row level security;
alter table scoring_rules           enable row level security;
alter table player_match_archive    enable row level security;
alter table team_strengths          enable row level security;
alter table player_predictions      enable row level security;
alter table prediction_evaluations  enable row level security;
alter table team_ratings            enable row level security;
```

**Ingest changes**
- In the `metrics` job, rows pruned from `player_gameweek_stats` are first upserted into `player_match_archive`, keyed by `players.code`.
- A new `predictions` job runs after `metrics`: fit team strengths, predict GW+1…GW+8, simulate ranges, and bump `data_version`.
- A new `evaluate` job runs when `gameweeks.data_checked` flips to true.
- **Pruning.** Keep the active model's predictions for all past GWs, because the accuracy page needs them. Delete inactive versions' rows after 30 days.
- **Storage.** About 700 players × 38 GWs × 8 leads ≈ 210k rows a season if every lead is kept. Store only the lead-1 to lead-6 rows needed for evaluation. That's fine on the Supabase free tier, but [verify] the 500 MB limit with indexes.

## 9. API endpoints

These follow the existing conventions: Public / Optional / User / Internal, pydantic models, and slowapi limits.

| Method & path | Auth | Description |
|---|---|---|
| `GET /predictions?gw_from=&gw_to=&position=&team=&max_cost=&sort=` | Optional | xPts table. Guests: GW+1..+3. Users: up to +6 (paid: +8, `format=csv`). Cached per `data_version`. |
| `GET /players/{id}/prediction?gws=6` | Optional | Component breakdown per GW, P10/P50/P90, and last 6 actual-vs-predicted. Extends `player_detail`. |
| `POST /rating` `{entry_id, horizon?}` | Optional | Squad Efficiency and leaks. Guests are forced to `horizon=1`. Uses `entry_cache` and `team_ratings`. Per-IP limit. |
| `POST /suggestions` (existing) | Optional | New optional body fields for users: `projection_mode`, `risk_profile`, `force_transfers` (int ≥ 1), `alternatives` (k ≤ 5; paid: k ≤ 10). Guests: model mode and balanced, as today. |
| `GET /me/agent/latest` (existing) | User | Plans now include `model_version`, xPts ranges, and component deltas in `transfers[].metric_deltas`. |
| `GET /accuracy?season=&gw=&position=` | Public | Rows from `prediction_evaluations` plus calibration. |
| `GET /model` | Public | Active model version, `trained_through`, changelog. |
| `POST /internal/predictions/recompute` | Internal | Triggered by the ingest workflow. |
| `POST /internal/predictions/evaluate?gw=` | Internal | After `data_checked`. |

**Chat harness additions** (CHATBOT_HARNESS_SPEC §6.3):
- A `get_predictions` tool (player IDs × GWs → compact xPts and components).
- A `get_squad_rating` tool.
- `get_player` and `run_transfer_optimiser` return xPts fields automatically.

## 10. Tier placement

| Capability | Guest | Free (Google sign-in) | Future paid |
|---|---|---|---|
| Next-GW xPts table | ✅ GW+1..+3 | ✅ GW+1..+6 | ✅ GW+1..+8, CSV export |
| Player xPts breakdown | ✅ | ✅ | ✅ |
| Squad Efficiency rating | ✅ N=1, no email | ✅ N=1/3/5 | ✅ plus history chart over the season |
| Transfer picks | ✅ N=1 (existing) | ✅ agent 1/3/5 (existing), model mode | Tilt mode with custom weights (already free today; **decision:** keep free), risk profiles, up to 10 alternatives, force-k transfers |
| Explanations | Template | Template | LLM-written (`LLMExplainer`, existing plan) |
| `/accuracy` page | ✅ | ✅ | ✅ (trust is a growth lever; never paywall it) |

**Rationale.** FFH paywalls the very first useful answer, and Reddit users resent it (R4: "removed all of this for free use"). FPLBud should give the core answer free and charge for depth and convenience.

## 11. Dependencies

- **Data:**
  - vaastav dataset backfill (licence and terms check, §6);
  - `players.code` mapping for cross-season joins;
  - continued `element_summaries` ingest.
- **Code:**
  - new `fplcore/predict/` package: `minutes.py`, `team_strength.py`, `components.py`, `simulate.py`, `evaluate.py`;
  - `scripts/backfill_history.py` and `scripts/backtest.py` (extend the existing one);
  - changes to `api/services.py:load_opt_players`;
  - `agent/runner.py` (records the model version);
  - `agent/chips.py` (re-tuned thresholds).
- **Libraries:** `numpy`, `scipy` / `statsmodels` (GLMs), `pandas` for training scripts only. Keep the API import path light: the API reads predictions from the DB and never trains.
- **Infra:**
  - GitHub Actions for training and backfill (minutes per run);
  - Supabase storage headroom;
  - no new paid services.
- **Specs:** CHATBOT_HARNESS_SPEC (tool additions); the sibling planner spec consumes `player_predictions`.

## 12. Phased milestones and acceptance criteria

| Phase | Scope | Acceptance criteria |
|---|---|---|
| **P0 History** (1 wk) | `player_match_archive`; backfill 2016-17 → 2025-26 from vaastav; archive-instead-of-prune in `metrics` | ≥ 95% of archive rows map to a `player_code`. Season point totals per player match FPL `history_past` within ±1 for 99% of players. Re-running the backfill is idempotent. |
| **P1 Baseline model + backtest** (2 wks) | Minutes model, team strengths, component xPts (no simulation), walk-forward harness, `prediction_evaluations` (backtest rows) | Backtest report for 2023-24 → 2025-26. The model beats the heuristic on MAE and Spearman in every season. The comparison with `ep_next` is reported whatever the result. A full season backtest runs in < 15 min in CI. |
| **P2 Production predictions** (1 wk) | `predictions` job, `player_predictions`, `model_versions`, `GET /predictions`, player breakdown | Predictions for GW+1..+8 are written within 10 min of each ingest. Every selectable player has a row (or `PROJ_FALLBACK`). The p95 API latency for `/predictions` is < 300 ms. |
| **P3 Optimiser on xPts** (1 wk) | `load_opt_players` switch (feature flag `XPTS_ENABLED`), tilt mode, re-tuned `HORIZON_SETTINGS` and chip thresholds via the decision backtest, new reason codes, UI xPts on plan cards | On a past-season decision backtest from 3 template squads, xPts plans score ≥ the heuristic plans' total points. Property tests (squad rules, budget, ≤3 per club) still pass. Guest `/suggestions` stays < 1 s p95. |
| **P4 Rating + accuracy page** (1 wk) | `POST /rating`, `team_ratings`, guest card, `/accuracy`, `evaluate` job | The rating returns in < 1 s for a guest. `/accuracy` updates within 2 h of `data_checked`. Numbers match a manual recomputation for one GW. |
| **P5 Uncertainty + paid depth** (1–2 wks) | Simulation P10/P90, risk profiles, alternatives k ≤ 10, LLM explanations behind the paid flag, chat tools | Empirical coverage of the P10–P90 interval is between 70% and 90% on the backtest. LLM explanations pass the existing grounding check in ≥ 98% of runs. |

## 13. Risks and open questions

**Risks**
- **The model may not beat `ep_next`.** FPL's own xP is decent. Mitigation: ship it as "explainable and published", be honest on `/accuracy`, and iterate (e.g. ensemble with `ep_next` as a feature; fine for internal use).
- **DC history is short** (2025/26 onward). Mitigation: shrink strongly toward position means, and flag low-confidence DC.
- **Rule changes each season** (scoring, chips, transfer banking). Mitigation: a `scoring_rules` table and a pre-season checklist.
- **Data terms** (FPL, Understat via vaastav). Mitigation: internal training only. Never republish raw historical rows; show only derived predictions and our own statistics.
- **The thresholds tuned on the heuristic scale will change behaviour** (more or fewer hits and chip calls). Mitigation: feature flag, decision backtest, release notes.
- **Compute on the free tier.** The nightly simulation is a few seconds, and training stays in CI. Mitigation: never train in the API.
- **Overclaiming.** Don't market "AI beats 99%" (FFH's style). Market measured accuracy only.

**Open questions**
1. Keep custom metric weights as a "tilt", or retire them in favour of xPts plus a few intuitive levers (risk, minutes certainty, fixture emphasis)?
2. Show xPts to one decimal, or rounded to whole points with the range, to discourage false precision?
3. Should the Squad Efficiency denominator use a fixed budget (team value + bank) or selling value? Proposed: selling value + bank, because that's what you can actually afford.
4. Paid tier pricing and billing provider are undecided. ARCHITECTURE §2A lists a paid tier as future.
5. Should the accuracy page include rival models? No. Compare only against FPL's `ep_next` and our own history, to avoid claims about competitors.
