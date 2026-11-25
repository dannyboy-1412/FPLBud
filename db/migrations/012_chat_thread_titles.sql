-- One title generation per chat thread. Fresh databases get the column from schema.sql.
set search_path = fpl, public;

alter table chat_threads
  add column if not exists title_generated boolean not null default false;

create table if not exists llm_title_usage (
  day           date primary key,
  calls         integer not null default 0 check (calls >= 0)
);
alter table llm_title_usage enable row level security;
