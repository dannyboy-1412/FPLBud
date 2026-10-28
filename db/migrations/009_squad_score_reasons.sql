-- Cached OpenRouter sentence for a squad score. Also created in schema.sql.
-- The key is the 15 players and their squad positions. News and projections do not change it.
set search_path = fpl, public;

create table if not exists squad_score_reasons (
  team_hash   text primary key,
  reason      text not null,
  created_at  timestamptz not null default now()
);

alter table squad_score_reasons enable row level security;
