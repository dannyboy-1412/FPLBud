-- Cached transfer plans. Also created in schema.sql for a fresh database.
set search_path = fpl, public;

create table if not exists suggested_transfers (
  user_id       uuid not null references auth.users(id) on delete cascade,
  entry_id      integer not null,
  gameweek      smallint not null,
  squad_hash    text not null,
  advice        jsonb not null,
  created_at    timestamptz not null default now(),
  primary key (user_id, entry_id, gameweek, squad_hash)
);

alter table suggested_transfers enable row level security;

drop policy if exists "suggested_transfers: read own" on suggested_transfers;
create policy "suggested_transfers: read own" on suggested_transfers
  for select to authenticated using ((select auth.uid()) = user_id);
