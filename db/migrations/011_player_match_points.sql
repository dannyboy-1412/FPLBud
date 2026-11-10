-- Season-long per-fixture points so chat can split a player's returns by FDR.
-- Wide player_gameweek_stats rows stay on the 8-round window.
-- Clearing history_minutes makes the next element_summaries job refetch everyone.
set search_path = fpl, public;

create table if not exists player_match_points (
  season_id     text not null,
  player_id     integer not null,
  fixture_id    integer not null,
  round         smallint not null,
  opponent_team smallint not null,
  was_home      boolean not null,
  minutes       smallint not null,
  starts        smallint not null,
  total_points  smallint not null,
  goals_scored  smallint not null,
  assists       smallint not null,
  clean_sheets  smallint not null,
  bonus         smallint not null,
  primary key (season_id, player_id, fixture_id),
  foreign key (season_id, player_id) references players(season_id, id)
);
create index if not exists player_match_points_player_idx
  on player_match_points (season_id, player_id);
alter table player_match_points enable row level security;

update players set history_minutes = null;
