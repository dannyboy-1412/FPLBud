-- Enough of Supabase auth for schema.sql to load into plain Postgres.
-- Grants live in grants.sql and run after the tables exist.

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key,
  email text,
  raw_user_meta_data jsonb not null default '{}'::jsonb
);

do $$
begin
  create role anon nologin;
exception
  when duplicate_object then null;
end
$$;

do $$
begin
  create role authenticated nologin;
exception
  when duplicate_object then null;
end
$$;

create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
