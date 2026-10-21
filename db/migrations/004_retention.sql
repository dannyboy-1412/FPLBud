-- Slim season-long points so wide match history can be pruned.
set search_path = fpl, public;

create table if not exists player_gw_points (
  season_id     text not null,
  player_id     integer not null,
  round         smallint not null,
  total_points  smallint not null,
  primary key (season_id, player_id, round),
  foreign key (season_id, player_id) references players(season_id, id)
);
alter table player_gw_points enable row level security;

insert into player_gw_points (season_id, player_id, round, total_points)
select season_id, player_id, round, sum(total_points)::smallint
  from player_gameweek_stats
 group by season_id, player_id, round
on conflict (season_id, player_id, round) do update
  set total_points = excluded.total_points;
