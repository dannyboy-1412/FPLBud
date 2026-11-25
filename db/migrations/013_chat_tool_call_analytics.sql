-- Keep tool-call analytics rows past thread pruning, record rejected and memoised
-- calls, and index analytics queries by name and created_at.
set search_path = fpl, public;

alter table chat_tool_calls
  alter column turn_id drop not null,
  drop constraint if exists chat_tool_calls_turn_id_fkey,
  add constraint chat_tool_calls_turn_id_fkey
    foreign key (turn_id) references chat_turns(id) on delete set null,
  add column if not exists user_id uuid references auth.users(id) on delete cascade,
  add column if not exists thread_id uuid,
  add column if not exists model text,
  add column if not exists cached boolean not null default false;

update chat_tool_calls c
   set user_id = coalesce(c.user_id, t.user_id),
       thread_id = coalesce(c.thread_id, t.thread_id),
       model = coalesce(c.model, t.model)
  from chat_turns t
 where c.turn_id = t.id
   and (c.user_id is null or c.thread_id is null or c.model is null);

create index if not exists chat_tool_calls_user_idx
  on chat_tool_calls (user_id) where user_id is not null;
create index if not exists chat_tool_calls_name_created_idx
  on chat_tool_calls (name, created_at);
create index if not exists chat_tool_calls_created_name_idx
  on chat_tool_calls (created_at, name);

create or replace function fpl.scrub_orphaned_chat_tool_calls() returns trigger
language plpgsql set search_path = '' as $$
begin
  update fpl.chat_tool_calls
     set args = null, result = null
   where turn_id = old.id
     and (args is not null or result is not null);
  return old;
end;
$$;

drop trigger if exists chat_turns_scrub_tool_calls on chat_turns;
create trigger chat_turns_scrub_tool_calls
  before delete on chat_turns
  for each row execute function fpl.scrub_orphaned_chat_tool_calls();
