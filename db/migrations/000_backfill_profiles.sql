-- Existing auth.users will not fire the sign-up trigger. Backfill profiles.
insert into public.profiles (id, display_name, avatar_url)
select
  u.id,
  coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name'),
  u.raw_user_meta_data->>'avatar_url'
from auth.users u
on conflict (id) do nothing;
