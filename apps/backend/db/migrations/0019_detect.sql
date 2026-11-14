-- 0019 — Disease detection schema: scans, chats, and chat messages.

create table if not exists public.detect_scans (
  id               uuid primary key default gen_random_uuid(),
  account_id       uuid not null references public.users(id) on delete cascade,
  farm_id          uuid references public.farms(id) on delete set null,
  disease_name     text not null,
  confidence       numeric(5, 4) not null default 0 check (confidence >= 0 and confidence <= 1),
  severity         text not null default 'watch' check (severity in ('watch','treat_now','clear')),
  crop             text not null default '',
  causes           text not null default '',
  treatment_steps  jsonb not null default '[]'::jsonb,
  rescan_timing    text not null default '',
  caution          text not null default '',
  image_url        text not null default '',
  image_path       text,
  created_at       timestamptz not null default now()
);
create index if not exists detect_scans_account_idx
  on public.detect_scans (account_id, created_at desc);
create index if not exists detect_scans_farm_idx on public.detect_scans (farm_id);

create table if not exists public.detect_chats (
  id          uuid primary key default gen_random_uuid(),
  account_id  uuid not null references public.users(id) on delete cascade,
  scan_id     uuid references public.detect_scans(id) on delete set null,
  title       text not null default 'Leaf scan',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists detect_chats_account_idx
  on public.detect_chats (account_id, updated_at desc);

create table if not exists public.detect_messages (
  id          uuid primary key default gen_random_uuid(),
  chat_id     uuid not null references public.detect_chats(id) on delete cascade,
  role        text not null check (role in ('farmer','detect')),
  content     text not null,
  created_at  timestamptz not null default now()
);
create index if not exists detect_messages_chat_idx
  on public.detect_messages (chat_id, created_at);

alter table public.detect_scans enable row level security;
alter table public.detect_chats enable row level security;
alter table public.detect_messages enable row level security;

do $$ begin
  create policy "detect_scans_select_own" on public.detect_scans for select using (true);
  create policy "detect_scans_insert_own" on public.detect_scans for insert with check (true);
  create policy "detect_scans_update_own" on public.detect_scans for update using (true);
  create policy "detect_scans_delete_own" on public.detect_scans for delete using (true);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy "detect_chats_select_own" on public.detect_chats for select using (true);
  create policy "detect_chats_insert_own" on public.detect_chats for insert with check (true);
  create policy "detect_chats_update_own" on public.detect_chats for update using (true);
  create policy "detect_chats_delete_own" on public.detect_chats for delete using (true);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy "detect_messages_select_own" on public.detect_messages for select using (true);
  create policy "detect_messages_insert_own" on public.detect_messages for insert with check (true);
  create policy "detect_messages_delete_own" on public.detect_messages for delete using (true);
exception when duplicate_object then null; end $$;
