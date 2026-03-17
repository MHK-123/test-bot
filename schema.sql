-- DungeonKeeper Supabase schema
-- Paste into Supabase SQL Editor and run.

-- 1) Cases table
create table if not exists public.cases (
  id bigserial primary key,
  reporter_id bigint not null,
  report_content text not null,
  attachment_urls jsonb,
  status text not null default 'OPEN',
  created_at timestamptz not null default now(),
  closed_at timestamptz,

  guild_id bigint,
  staff_channel_id bigint,
  staff_message_id bigint unique,
  thread_id bigint
);

-- 2) Blacklist table
create table if not exists public.blacklist (
  user_id bigint primary key,
  created_at timestamptz not null default now()
);

-- 3) DM sessions table
create table if not exists public.dm_sessions (
  user_id bigint primary key,
  expires_at timestamptz not null
);

-- Helpful indexes (optional but recommended)
create index if not exists idx_cases_reporter_id on public.cases (reporter_id);
create index if not exists idx_cases_status on public.cases (status);
create index if not exists idx_dm_sessions_expires_at on public.dm_sessions (expires_at);

-- Optional: turn off RLS for bot-only usage (service role works regardless)
-- alter table public.cases disable row level security;
-- alter table public.blacklist disable row level security;
-- alter table public.dm_sessions disable row level security;

