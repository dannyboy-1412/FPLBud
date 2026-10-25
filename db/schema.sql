-- FPLBud — Supabase Postgres schema (v1)
-- Every column was checked against the live FPL API on 2026-10-12 (2026/27 season, GW6 current).
-- Money is stored the way FPL stores it: integer tenths of £m (for example 51 = £5.1m).

create schema if not exists fpl;
set search_path = fpl, public;

-- ---------- Reference data (from bootstrap-static) ----------
create table seasons (
  id            text primary key,              -- '2026/27'
  is_current    boolean not null default false,
  total_players integer not null default 0     -- bootstrap-static.total_players
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
  highest_score integer,                       -- null until the GW is finished
  most_captained integer,                      -- element id; null until published
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
  transfers_in        integer not null default 0,
  transfers_out       integer not null default 0,
  event_points        integer not null default 0,
  goals_scored        integer not null default 0,
  assists             integer not null default 0,
  clean_sheets        integer not null default 0,
  bonus               integer not null default 0,
  bps                 integer not null default 0,
  defensive_contribution integer not null default 0,
  ict_index           numeric(5,1),
  penalties_order     smallint,
  corners_and_indirect_freekicks_order smallint,
  direct_freekicks_order smallint,
  form          numeric(4,1) not null,         -- FPL's own form: average points per match over roughly the last 30 days
  points_per_game numeric(4,1) not null,
  total_points  integer not null,
  minutes       integer not null,
  history_minutes integer,                     -- season minutes last saved from element-summary; null = never fetched
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
create index player_daily_snapshots_date_idx on player_daily_snapshots (season_id, snapshot_date);

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

-- Slim season-long points for captain returns. Wide match rows are pruned.
create table player_gw_points (
  season_id     text not null,
  player_id     integer not null,
  round         smallint not null,
  total_points  smallint not null,
  primary key (season_id, player_id, round),
  foreign key (season_id, player_id) references players(season_id, id)
);

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
  fixture_raw   numeric(6,3),  fixture_score   numeric(5,4),   -- mean ease = (5 - FDR)/4 across that GW's fixtures
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

-- ---------- Users: profiles (Supabase Auth, Google OAuth) ----------
-- Lives in `public` (Supabase convention, exposed to supabase-js); everything else is in `fpl`.
create table public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text,                          -- from Google metadata at sign-up
  avatar_url    text,
  fpl_entry_id  integer check (fpl_entry_id > 0),   -- entered once at onboarding; public team ID
  fpl_team_name text,                          -- cached for display
  weights       jsonb not null default
    '{"form":0.30,"fixture":0.25,"home":0.10,"xgi":0.35,"value":0.15,"minutes":0.15,"trend":0}'
    check (jsonb_typeof(weights) = 'object'),
  default_horizon smallint not null default 3 check (default_horizon in (1,3,5)),
  max_hits      smallint not null default 1 check (max_hits between 0 and 3),
  onboarded_at  timestamptz,                   -- set when the team ID is first saved
  last_active_at timestamptz not null default now(),  -- drives the background re-run cutoff
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index profiles_entry_idx  on public.profiles (fpl_entry_id);
create index profiles_active_idx on public.profiles (last_active_at) where fpl_entry_id is not null;

alter table public.profiles enable row level security;
-- Users can read and update only their own row. No insert/delete policies:
-- rows are created by the trigger below and removed by cascade from auth.users.
create policy "profiles: read own"   on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "profiles: update own" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- Create a profile row automatically when someone signs in with Google for the first time.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (new.id,
          coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
          new.raw_user_meta_data->>'avatar_url');
  return new;
end;
$$;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create function public.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin new.updated_at := now(); return new; end;
$$;
create trigger profiles_touch_updated_at
  before update on public.profiles
  for each row execute function public.touch_updated_at();

-- Shared cache of PUBLIC FPL entry responses (guests and users), 5-minute TTL. Holds no user data.
create table entry_cache (
  entry_id      integer not null,
  event         smallint not null,
  payload       jsonb not null,                -- merged entry + picks + history + transfers
  fetched_at    timestamptz not null default now(),
  primary key (entry_id, event)
);

-- Finished-GW picks for signed-in users (captain returns). Past GWs never change, so one fetch each.
create table entry_event_picks (
  entry_id      integer not null,
  event         smallint not null,
  picks         jsonb not null,                -- [{element, position, multiplier, is_captain, is_vice_captain}]
  active_chip   text,
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

-- Teams the agent keeps re-running for: signed-in users only.
-- Free tier: one row per user (enforced in the API); PK allows multiple teams for a future paid tier.
-- Weights come from public.profiles; the inactivity cutoff uses profiles.last_active_at.
create table tracked_entries (
  user_id       uuid not null references auth.users(id) on delete cascade,
  entry_id      integer not null,
  overrides     jsonb,                         -- {free_transfers, bank, squad[15]} if user-edited
  created_at    timestamptz not null default now(),
  primary key (user_id, entry_id)
);
create index tracked_entries_entry_idx on tracked_entries (entry_id);

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
  created_by    uuid references auth.users(id) on delete cascade,  -- snapshots are only created for signed-in users
  content_hash  text not null,                 -- dedupe identical re-imports
  fetched_at    timestamptz not null default now(),
  unique (entry_id, created_by, content_hash)
);
create index team_snapshots_entry_idx on team_snapshots (entry_id, fetched_at desc);

-- Job queue + run history. Claimed with FOR UPDATE SKIP LOCKED.
create table agent_runs (
  id            bigserial primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  entry_id      integer not null,
  snapshot_id   bigint not null references team_snapshots(id) on delete cascade,
  trigger       text not null check (trigger in
                  ('import','user_rerun','data_refresh','pre_deadline','post_deadline')),
  priority      smallint not null default 0,   -- 0 = user-facing, 10 = background
  status        text not null default 'queued' check (status in
                  ('queued','running','succeeded','failed','cancelled')),
  stage         text,                          -- context | horizon_1 | horizon_3 | horizon_5 | chips | explain
  progress      smallint not null default 0 check (progress between 0 and 100),
  weights       jsonb not null,                -- copied from profiles.weights at enqueue time
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
create index agent_runs_user_idx   on agent_runs (user_id, created_at desc);
create index agent_runs_stale_idx  on agent_runs (started_at) where status = 'running';
-- At most one pending/active run per (user, team): repeat imports reuse it.
create unique index agent_runs_one_active_per_user_entry
  on agent_runs (user_id, entry_id) where status in ('queued','running');

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

-- Daily LLM call counter (OpenRouter). Enforces LLM_DAILY_CALL_CAP.
create table llm_usage (
  day           date primary key,
  calls         integer not null default 0 check (calls >= 0)
);
alter table llm_usage enable row level security;

-- One suggested XI per user, team, gameweek, and hash of the 15 players plus weights.
-- News and metric rebuilds do not change the key. Ingest deletes earlier gameweeks.
create table suggested_lineups (
  user_id       uuid not null references auth.users(id) on delete cascade,
  entry_id      integer not null,
  gameweek      smallint not null,
  squad_hash    text not null,
  lineup        jsonb not null,
  created_at    timestamptz not null default now(),
  primary key (user_id, entry_id, gameweek, squad_hash)
);
alter table suggested_lineups enable row level security;

-- RLS: FastAPI and the ingest job connect via DATABASE_URL (server-side, bypasses RLS) and enforce
-- ownership in code (run.user_id = JWT sub). Policies below are defence in depth and would allow
-- future Supabase Realtime for owners. Everything without a policy is closed to anon/authenticated.
alter table tracked_entries   enable row level security;
alter table team_snapshots    enable row level security;
alter table agent_runs        enable row level security;
alter table agent_suggestions enable row level security;

create policy "tracked_entries: read own" on tracked_entries
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "suggested_lineups: read own" on suggested_lineups
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "agent_runs: read own" on agent_runs
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "agent_suggestions: read own" on agent_suggestions
  for select to authenticated using (exists (
    select 1 from agent_runs r where r.id = agent_suggestions.run_id and r.user_id = (select auth.uid())));

-- Reference data has no user content: enable RLS with no policies (API-only access).
alter table seasons enable row level security;  alter table teams enable row level security;
alter table positions enable row level security; alter table gameweeks enable row level security;
alter table fixtures enable row level security;  alter table players enable row level security;
alter table player_daily_snapshots enable row level security;
alter table player_gameweek_stats enable row level security;
alter table player_gw_points enable row level security;
alter table player_metrics enable row level security;
alter table entry_cache enable row level security; alter table ingest_runs enable row level security;
alter table data_versions enable row level security;
alter table entry_event_picks enable row level security;

-- Worker claim query (reference, used by fplcore.agent):
-- update agent_runs set status='running', started_at=now(), attempts=attempts+1, locked_by=$1
--  where id = (select id from agent_runs where status='queued'
--              order by priority, created_at for update skip locked limit 1)
--  returning *;
