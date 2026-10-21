-- Extra FPL fields + finished-GW picks cache for dashboard stats sections.
set search_path = fpl, public;

alter table seasons add column if not exists total_players integer not null default 0;

alter table gameweeks add column if not exists highest_score integer;
alter table gameweeks add column if not exists most_captained integer;

alter table players add column if not exists transfers_in integer not null default 0;
alter table players add column if not exists transfers_out integer not null default 0;
alter table players add column if not exists event_points integer not null default 0;
alter table players add column if not exists goals_scored integer not null default 0;
alter table players add column if not exists assists integer not null default 0;
alter table players add column if not exists clean_sheets integer not null default 0;
alter table players add column if not exists bonus integer not null default 0;
alter table players add column if not exists bps integer not null default 0;
alter table players add column if not exists defensive_contribution integer not null default 0;
alter table players add column if not exists ict_index numeric(5,1);
alter table players add column if not exists penalties_order smallint;
alter table players add column if not exists corners_and_indirect_freekicks_order smallint;
alter table players add column if not exists direct_freekicks_order smallint;

create index if not exists player_daily_snapshots_date_idx
  on player_daily_snapshots (season_id, snapshot_date);

create table if not exists entry_event_picks (
  entry_id      integer not null,
  event         smallint not null,
  picks         jsonb not null,
  active_chip   text,
  fetched_at    timestamptz not null default now(),
  primary key (entry_id, event)
);
alter table entry_event_picks enable row level security;
