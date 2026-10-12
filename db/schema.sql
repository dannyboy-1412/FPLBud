-- FPL Assistant — Supabase Postgres schema (v1)
-- Every column was checked against the live FPL API on 2026-10-12 (2026/27 season, GW6 current).
-- Money is stored the way FPL stores it: integer tenths of £m (for example 51 = £5.1m).

create schema if not exists fpl;
set search_path = fpl, public;

-- ---------- Reference data (from bootstrap-static) ----------
create table seasons (
  id            text primary key,              -- '2026/27'
  is_current    boolean not null default false
);

create table teams (
  season_id     text not null references seasons(id),
  id            smallint not null,             -- bootstrap teams[].id (1..20, season-specific)
  code          integer not null,              -- stable across seasons
  name          text not null,
  short_name    text not null,
  strength_overall_home smallint,
  strength_overall_away smallint,
  strength_attack_home  smallint,              -- NOTE: currently 0 for every team; don't rely on it
  strength_attack_away  smallint,
  strength_defence_home smallint,
  strength_defence_away smallint,
  updated_at    timestamptz not null default now(),
  primary key (season_id, id)
);

create table positions (                        -- element_types
  id            smallint primary key,          -- 1 GKP, 2 DEF, 3 MID, 4 FWD
  short_name    text not null,
  squad_select  smallint not null,             -- 2/5/5/3
  squad_min_play smallint not null,
  squad_max_play smallint not null
);

create table gameweeks (                        -- events
  season_id     text not null references seasons(id),
  id            smallint not null,             -- 1..38
  name          text not null,
  deadline_time timestamptz not null,
  is_current    boolean not null,
  is_next       boolean not null,
  is_previous   boolean not null,
  finished      boolean not null,
  data_checked  boolean not null,
  average_entry_score integer,
  primary key (season_id, id)
);

create table fixtures (
  season_id     text not null references seasons(id),
  id            integer not null,
  event         smallint,                      -- null = unscheduled/postponed
  kickoff_time  timestamptz,
  team_h        smallint not null,
  team_a        smallint not null,
  team_h_difficulty smallint not null,         -- 1..5 FDR from the home team's point of view
  team_a_difficulty smallint not null,
  team_h_score  smallint,
  team_a_score  smallint,
  started       boolean,
  finished      boolean not null,
  updated_at    timestamptz not null default now(),
  primary key (season_id, id),
  foreign key (season_id, team_h) references teams(season_id, id),
  foreign key (season_id, team_a) references teams(season_id, id)
);
create index fixtures_event_idx on fixtures (season_id, event);

-- ---------- Players: latest snapshot (bootstrap-static elements) ----------
create table players (
  season_id     text not null references seasons(id),
  id            integer not null,              -- element id (season-specific)
  code          integer not null,              -- stable across seasons
  web_name      text not null,
  first_name    text,
  second_name   text,
  team_id       smallint not null,
  position_id   smallint not null references positions(id),
  status        char(1) not null,              -- a, d, i, s, u (seen live)
  news          text,
  chance_of_playing_this_round smallint,       -- null / 0 / 25 / 50 / 75 / 100
  chance_of_playing_next_round smallint,
  now_cost      smallint not null,
  cost_change_start smallint not null,         -- now_cost - cost_change_start = price at season start
  cost_change_event smallint not null,
  selected_by_percent numeric(5,1) not null,
  transfers_in_event  integer not null,
  transfers_out_event integer not null,
  form          numeric(4,1) not null,         -- FPL's own form: average points per match over roughly the last 30 days
  points_per_game numeric(4,1) not null,
  total_points  integer not null,
  minutes       integer not null,
  starts        integer not null,
  expected_goals              numeric(6,2) not null,
  expected_assists            numeric(6,2) not null,
  expected_goal_involvements  numeric(6,2) not null,
  expected_goals_conceded     numeric(6,2) not null,
  ep_next       numeric(4,1),                  -- FPL's own expected points (used only for comparison)
  can_transact  boolean not null,
  removed       boolean not null default false,
  updated_at    timestamptz not null default now(),
  primary key (season_id, id),
  foreign key (season_id, team_id) references teams(season_id, id)
);
create index players_team_idx on players (season_id, team_id);
create index players_pos_idx  on players (season_id, position_id);

-- Daily price/ownership snapshots for the "trends" metric. Only bootstrap gives
-- a live view of this, so we keep our own history.
create table player_daily_snapshots (
  season_id     text not null,
  player_id     integer not null,
  snapshot_date date not null,
  now_cost      smallint not null,
  selected_by_percent numeric(5,1) not null,
  transfers_in_event  integer not null,
  transfers_out_event integer not null,
  primary key (season_id, player_id, snapshot_date),
  foreign key (season_id, player_id) references players(season_id, id)
);

-- ---------- Per-match history (element-summary/{id}.history, or event/{gw}/live) ----------
create table player_gameweek_stats (
  season_id     text not null,
  player_id     integer not null,
  fixture_id    integer not null,              -- a double gameweek gives 2 rows for the same round
  round         smallint not null,
  opponent_team smallint not null,
  was_home      boolean not null,
  minutes       smallint not null,
  starts        smallint not null,
  total_points  smallint not null,
  goals_scored  smallint not null,
  assists       smallint not null,
  clean_sheets  smallint not null,
  goals_conceded smallint not null,
  bonus         smallint not null,
  bps           smallint not null,
  saves         smallint not null,
  defensive_contribution smallint not null,
  expected_goals              numeric(5,2) not null,
  expected_assists            numeric(5,2) not null,
  expected_goal_involvements  numeric(5,2) not null,
  expected_goals_conceded     numeric(5,2) not null,
  ict_index     numeric(5,1) not null,
  value         smallint not null,             -- price at the time of the match
  selected      integer not null,
  transfers_balance integer not null,
  primary key (season_id, player_id, fixture_id),
  foreign key (season_id, player_id) references players(season_id, id)
);
create index pgs_round_idx on player_gameweek_stats (season_id, round);

-- ---------- Precomputed metric components (written by the ingest job) ----------
-- One row per player per *target* gameweek (the next GW, and later the next N).
-- Raw values are kept for display; *_score columns are normalised to 0..1 within position.
create table player_metrics (
  season_id     text not null,
  player_id     integer not null,
  computed_for_gw smallint not null,           -- the GW these scores are meant to predict
  horizon       smallint not null default 1,   -- number of GWs aggregated, starting at computed_for_gw
  -- default metrics
  form_raw      numeric(6,3),  form_score      numeric(5,4),
  fixture_raw   numeric(6,3),  fixture_score   numeric(5,4),   -- average (6 - FDR) across the horizon
  home_raw      numeric(6,3),  home_score      numeric(5,4),   -- home share across the horizon, with a split adjustment
  xgi_raw       numeric(6,3),  xgi_score       numeric(5,4),   -- position-weighted xG/xA per 90 (recent plus season blend)
  -- optional metrics
  value_raw     numeric(6,3),  value_score     numeric(5,4),   -- points per £m
  minutes_raw   numeric(6,3),  minutes_score   numeric(5,4),   -- start probability proxy
  trend_raw     numeric(8,3),  trend_score     numeric(5,4),   -- net transfers / ownership momentum
  fixture_count smallint not null,             -- 0 = blank, 2 = double, across the horizon
  availability  numeric(4,3) not null,         -- chance_of_playing/100 (1.0 when null and status 'a')
  computed_at   timestamptz not null default now(),
  primary key (season_id, player_id, computed_for_gw, horizon),
  foreign key (season_id, player_id) references players(season_id, id)
);
create index pm_gw_idx on player_metrics (season_id, computed_for_gw, horizon);

-- ---------- Users (optional in v1; anonymous use works without it) ----------
create table user_settings (
  user_id       uuid primary key references auth.users(id) on delete cascade,  -- Supabase Auth
  fpl_entry_id  integer,
  weights       jsonb not null default
    '{"form":0.30,"fixture":0.25,"home":0.10,"xgi":0.35,"value":0,"minutes":0,"trend":0}',
  horizon       smallint not null default 3 check (horizon between 1 and 6),
  max_hits      smallint not null default 1 check (max_hits between 0 and 3),
  updated_at    timestamptz not null default now()
);
alter table user_settings enable row level security;
create policy "own settings" on user_settings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Squad-import cache, so repeat requests don't hit FPL again (short TTL)
create table entry_cache (
  entry_id      integer not null,
  event         smallint not null,
  payload       jsonb not null,                -- merged entry + picks + history + transfers
  fetched_at    timestamptz not null default now(),
  primary key (entry_id, event)
);

-- Ingest bookkeeping
create table ingest_runs (
  id            bigserial primary key,
  job           text not null,                 -- 'bootstrap', 'fixtures', 'element_summaries', 'metrics'
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  ok            boolean,
  detail        text
);

-- =====================================================================
-- Team agent (see ARCHITECTURE.md §6A)
-- =====================================================================

-- Every metrics recompute bumps this; agent runs record which version they used.
create table data_versions (
  id            bigserial primary key,         -- = data_version
  ingest_run_id bigint references ingest_runs(id),
  next_gw       smallint not null,
  created_at    timestamptz not null default now()
);

-- Teams the agent keeps re-running for (anonymous users included; keyed by public FPL entry id)
create table tracked_entries (
  entry_id      integer primary key,
  user_id       uuid references auth.users(id) on delete set null,
  weights       jsonb not null,                -- weights used for background re-runs
  overrides     jsonb,                         -- {free_transfers, bank, squad[15]} if user-edited
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz not null default now()   -- background re-runs only if seen within 14 days
);
create index tracked_entries_seen_idx on tracked_entries (last_seen_at);

-- Immutable team context built at import (§6, §6A.1)
create table team_snapshots (
  id            bigserial primary key,
  entry_id      integer not null,
  event         smallint not null,             -- GW the picks belong to (entry.current_event)
  season_id     text not null references seasons(id),
  picks         jsonb not null,                -- [{element, position, is_captain, is_vice_captain, multiplier}]
  bank          smallint not null,             -- tenths of £m
  team_value    smallint not null,
  free_transfers smallint not null,            -- estimated (or overridden)
  selling_prices jsonb not null,               -- {"<element>": price}, estimated
  chips_available jsonb not null,              -- [{name, stop_event}] for the current half
  chips_used    jsonb not null,                -- [{name, event}]
  active_chip   text,
  flags         jsonb not null default '[]',   -- [{element, status, chance_of_playing_next_round, news}]
  overrides     jsonb,                         -- user edits applied on top of FPL data
  content_hash  text not null,                 -- dedupe identical re-imports
  fetched_at    timestamptz not null default now(),
  unique (entry_id, content_hash)
);
create index team_snapshots_entry_idx on team_snapshots (entry_id, fetched_at desc);

-- Job queue + run history. Claimed with FOR UPDATE SKIP LOCKED.
create table agent_runs (
  id            bigserial primary key,
  entry_id      integer not null,
  snapshot_id   bigint not null references team_snapshots(id) on delete cascade,
  trigger       text not null check (trigger in
                  ('import','user_rerun','data_refresh','pre_deadline','post_deadline')),
  priority      smallint not null default 0,   -- 0 = user-facing, 10 = background
  status        text not null default 'queued' check (status in
                  ('queued','running','succeeded','failed','cancelled')),
  stage         text,                          -- context | horizon_1 | horizon_3 | horizon_5 | chips | explain
  progress      smallint not null default 0 check (progress between 0 and 100),
  weights       jsonb not null,
  weights_hash  text not null,
  data_version  bigint references data_versions(id),
  attempts      smallint not null default 0,
  locked_by     text,                          -- worker id (api-<pid> / gha-<run>)
  error         text,
  created_at    timestamptz not null default now(),
  started_at    timestamptz,
  finished_at   timestamptz
);
create index agent_runs_queue_idx  on agent_runs (priority, created_at) where status = 'queued';
create index agent_runs_entry_idx  on agent_runs (entry_id, created_at desc);
create index agent_runs_stale_idx  on agent_runs (started_at) where status = 'running';
-- At most one pending/active run per team: repeat imports reuse it.
create unique index agent_runs_one_active_per_entry
  on agent_runs (entry_id) where status in ('queued','running');

-- One row per horizon per run (N = 1, 3, 5)
create table agent_suggestions (
  run_id        bigint not null references agent_runs(id) on delete cascade,
  horizon       smallint not null check (horizon in (1,3,5)),
  plan          jsonb not null,                -- HorizonPlan: transfers, hits, xi, bench, captain, vice, projections
  alternatives  jsonb not null default '[]',   -- roll / fewer-transfer plans
  chip_advice   jsonb not null default '[]',   -- [{chip, recommend, best_gw, expected_gain, reason_codes}]
  reason_codes  text[] not null default '{}',
  gain_vs_roll  numeric(6,2),
  hits          smallint not null default 0,
  plan_hash     text not null,                 -- reuse explanation when the plan is unchanged
  explanation   text,
  explanation_source text check (explanation_source in ('template','llm')),
  created_at    timestamptz not null default now(),
  primary key (run_id, horizon)
);
create index agent_suggestions_plan_hash_idx on agent_suggestions (plan_hash);

-- All access goes through FastAPI (service role). RLS on, with no anon policies = closed to browsers.
alter table tracked_entries   enable row level security;
alter table team_snapshots    enable row level security;
alter table agent_runs        enable row level security;
alter table agent_suggestions enable row level security;

-- Worker claim query (reference, used by fplcore.agent):
-- update agent_runs set status='running', started_at=now(), attempts=attempts+1, locked_by=$1
--  where id = (select id from agent_runs where status='queued'
--              order by priority, created_at for update skip locked limit 1)
--  returning *;
