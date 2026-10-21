-- Idempotent: llm_usage is also in schema.sql for fresh applies.
create table if not exists fpl.llm_usage (
  day           date primary key,
  calls         integer not null default 0 check (calls >= 0)
);
alter table fpl.llm_usage enable row level security;
