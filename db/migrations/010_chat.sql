-- Chat agent: threads, messages, traces, memory, usage.
-- Also merged into db/schema.sql. hit_tolerance is not a memory key;
-- profiles.max_hits is the source of truth for how many hits a plan may take.
set search_path = fpl, public;

create table chat_threads (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  title         text,
  context       jsonb,
  context_data_version bigint,
  summary       text,
  message_count integer not null default 0,
  archived_at   timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index chat_threads_user_idx on chat_threads (user_id, updated_at desc) where archived_at is null;

create table chat_messages (
  id            bigint generated always as identity primary key,
  thread_id     uuid not null references chat_threads(id) on delete cascade,
  turn_id       bigint,
  seq           integer not null,
  role          text not null check (role in ('user','assistant','tool','system')),
  content       text not null,
  tool_call_id  text,
  tool_calls    jsonb,
  citations     jsonb,
  client_msg_id text,
  feedback      smallint check (feedback in (-1, 1)),
  feedback_reason text,
  created_at    timestamptz not null default now(),
  unique (thread_id, seq)
);
create unique index chat_messages_idem_idx on chat_messages (thread_id, client_msg_id) where client_msg_id is not null;

create table chat_turns (
  id            bigint generated always as identity primary key,
  thread_id     uuid not null references chat_threads(id) on delete cascade,
  user_id       uuid not null references auth.users(id) on delete cascade,
  status        text not null default 'running' check (status in ('running','ok','fallback','error','blocked','abandoned','capped')),
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  prompt_version text not null,
  rules_version  text,
  model         text,
  data_version  bigint,
  rounds        smallint not null default 0,
  tool_call_count smallint not null default 0,
  input_tokens  integer not null default 0,
  output_tokens integer not null default 0,
  cached_tokens integer not null default 0,
  cost_usd      numeric(10,6),
  latency_ms    integer,
  first_token_ms integer,
  grounding_flags jsonb,
  repaired      boolean not null default false,
  error_code    text,
  user_text_len integer,
  client        text
);
create unique index chat_turns_one_running on chat_turns (thread_id) where status = 'running';
create index chat_turns_user_day_idx on chat_turns (user_id, started_at desc);

create table chat_tool_calls (
  id            bigint generated always as identity primary key,
  turn_id       bigint not null references chat_turns(id) on delete cascade,
  round         smallint not null,
  name          text not null,
  args          jsonb,
  ok            boolean not null,
  error_code    text,
  result_tokens integer,
  result        jsonb,
  duration_ms   integer,
  created_at    timestamptz not null default now()
);
create index chat_tool_calls_turn_idx on chat_tool_calls (turn_id);

create table chat_memory (
  user_id       uuid not null references auth.users(id) on delete cascade,
  key           text not null check (key in (
                  'risk_appetite','favourite_team','avoid_player_ids','prefers_differentials','notes_short')),
  value         text not null check (length(value) <= 80),
  source_message_id bigint references chat_messages(id) on delete set null,
  confirmed_at  timestamptz not null default now(),
  primary key (user_id, key)
);

create table chat_memory_proposals (
  id            bigint generated always as identity primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  thread_id     uuid not null references chat_threads(id) on delete cascade,
  key           text not null,
  value         text not null check (length(value) <= 80),
  status        text not null default 'pending' check (status in ('pending','confirmed','dismissed','expired')),
  created_at    timestamptz not null default now()
);

create table chat_usage (
  user_id       uuid not null references auth.users(id) on delete cascade,
  day           date not null,
  turns         integer not null default 0 check (turns >= 0),
  input_tokens  bigint  not null default 0,
  output_tokens bigint  not null default 0,
  cost_usd      numeric(10,6) not null default 0,
  optimiser_calls integer not null default 0,
  primary key (user_id, day)
);
create table chat_usage_global (
  day           date primary key,
  turns         integer not null default 0,
  cost_usd      numeric(10,6) not null default 0
);

alter table chat_threads  enable row level security;
alter table chat_messages enable row level security;
alter table chat_turns    enable row level security;
alter table chat_tool_calls enable row level security;
alter table chat_memory   enable row level security;
alter table chat_memory_proposals enable row level security;
alter table chat_usage    enable row level security;
alter table chat_usage_global enable row level security;

create policy "chat_threads: own"  on chat_threads  for select to authenticated using ((select auth.uid()) = user_id);
create policy "chat_messages: own" on chat_messages for select to authenticated using (exists (
  select 1 from chat_threads t where t.id = chat_messages.thread_id and t.user_id = (select auth.uid())));
create policy "chat_memory: own read"   on chat_memory for select to authenticated using ((select auth.uid()) = user_id);
create policy "chat_memory: own delete" on chat_memory for delete to authenticated using ((select auth.uid()) = user_id);
