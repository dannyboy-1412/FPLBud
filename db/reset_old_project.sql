-- Drop old-app objects while keeping the auth schema (users + identities).
-- Review scripts/db_inventory.py output before running.

-- Custom triggers on auth.users (old handle_new_user etc.)
do $$
declare
  r record;
begin
  for r in
    select t.tgname
    from pg_trigger t
    join pg_class c on c.oid = t.tgrelid
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'auth' and c.relname = 'users' and not t.tgisinternal
  loop
    execute format('drop trigger if exists %I on auth.users', r.tgname);
  end loop;
end $$;

-- Drop leftover public handle_new_user / updated_at helpers if present
drop function if exists public.handle_new_user() cascade;
drop function if exists public.touch_updated_at() cascade;

-- Drop every table / view in public
do $$
declare
  r record;
begin
  for r in
    select table_name
    from information_schema.views
    where table_schema = 'public'
  loop
    execute format('drop view if exists public.%I cascade', r.table_name);
  end loop;

  for r in
    select tablename
    from pg_tables
    where schemaname = 'public'
  loop
    execute format('drop table if exists public.%I cascade', r.tablename);
  end loop;

  for r in
    select n.nspname, t.typname
    from pg_type t
    join pg_namespace n on n.oid = t.typnamespace
    where n.nspname = 'public' and t.typtype = 'e'
  loop
    execute format('drop type if exists %I.%I cascade', r.nspname, r.typname);
  end loop;

  for r in
    select n.nspname as schema, p.proname as name, pg_get_function_identity_arguments(p.oid) as args
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
  loop
    execute format('drop function if exists %I.%I(%s) cascade', r.schema, r.name, r.args);
  end loop;
end $$;

-- Drop custom schemas the old app may have created
do $$
declare
  r record;
  keep text[] := array[
    'public','auth','storage','realtime','extensions','graphql','graphql_public',
    'vault','pgsodium','pgsodium_masks','supabase_functions','supabase_migrations',
    'net','cron','pgbouncer','information_schema','pg_catalog','pg_toast'
  ];
begin
  for r in
    select nspname from pg_namespace
    where nspname <> all(keep) and nspname not like 'pg_%'
  loop
    execute format('drop schema if exists %I cascade', r.nspname);
  end loop;
end $$;

-- Unschedule leftover cron jobs
do $$
declare
  r record;
begin
  if exists (select 1 from pg_namespace where nspname = 'cron') then
    for r in select jobid from cron.job loop
      perform cron.unschedule(r.jobid);
    end loop;
  end if;
exception when undefined_table then
  null;
end $$;

-- Storage objects are protected by a trigger; skip if the API is required.
do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'storage') then
    begin
      delete from storage.objects;
      delete from storage.buckets;
    exception when others then
      raise notice 'storage tables left in place (use Storage API to empty buckets)';
    end;
  end if;
end $$;
