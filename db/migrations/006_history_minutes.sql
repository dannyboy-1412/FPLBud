-- Bootstrap overwrites players.minutes on every price run, before the history
-- job can see who changed. This column is the minute total last saved from
-- element-summary, and it is the only watermark that job should trust.
set search_path = fpl, public;

alter table players add column if not exists history_minutes integer;
