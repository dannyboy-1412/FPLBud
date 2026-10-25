-- Value and minutes security are on by default. Profiles still at the old
-- zeros pick up 0.15. A weight someone has already set is left alone.
set search_path = fpl, public;

alter table public.profiles
  alter column weights set default
    '{"form":0.30,"fixture":0.25,"home":0.10,"xgi":0.35,"value":0.15,"minutes":0.15,"trend":0}'::jsonb;

update public.profiles
set weights = jsonb_set(weights, '{value}', '0.15')
where coalesce((weights->>'value')::numeric, 0) = 0;

update public.profiles
set weights = jsonb_set(weights, '{minutes}', '0.15')
where coalesce((weights->>'minutes')::numeric, 0) = 0;
