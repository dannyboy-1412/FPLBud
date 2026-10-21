-- Remove leftover tables from the previous app. Keep public.profiles.
drop table if exists public.ai_runs cascade;
drop table if exists public.document_versions cascade;
drop table if exists public.documents cascade;
drop table if exists public.files cascade;
drop table if exists public.projects cascade;
drop table if exists public.users cascade;
drop schema if exists drizzle cascade;
