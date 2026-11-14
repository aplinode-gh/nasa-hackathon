-- 0018 — Profit / Loss calculator schema.
-- Season-level cost tracking, expenses, and projected costs.
-- crop_id stores the crop slug used by the farmer app (e.g. 'wheat').

create table if not exists public.seasons (
  id             uuid primary key default gen_random_uuid(),
  account_id     uuid not null references public.users(id) on delete cascade,
  farm_id        uuid not null references public.farms(id) on delete cascade,
  crop_id        text not null,
  season         text not null,
  year           text not null,
  start_date     date not null,
  acres          numeric(10, 2) not null check (acres > 0),
  status         text not null default 'active',
  expected_yield numeric(12, 2),
  expected_price numeric(12, 2),
  actual_yield   numeric(12, 2),
  actual_price   numeric(14, 2),
  archived_at    timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists seasons_account_idx
  on public.seasons (account_id, archived_at, created_at desc);
create index if not exists seasons_farm_idx on public.seasons (farm_id);

create table if not exists public.expenses (
  id          uuid primary key default gen_random_uuid(),
  season_id   uuid not null references public.seasons(id) on delete cascade,
  account_id  uuid not null references public.users(id) on delete cascade,
  category    text not null check (category in ('seed','fertilizer','labor','irrigation','transport','other')),
  amount      numeric(14, 2) not null check (amount > 0),
  date        date not null,
  note        text,
  created_at  timestamptz not null default now()
);
create index if not exists expenses_season_idx
  on public.expenses (season_id, date desc, created_at desc);
create index if not exists expenses_account_idx on public.expenses (account_id);

create table if not exists public.projected_costs (
  id                    uuid primary key default gen_random_uuid(),
  season_id             uuid not null references public.seasons(id) on delete cascade,
  category              text not null check (category in ('seed','fertilizer','labor','irrigation','transport')),
  per_acre_cost_pkr     numeric(14, 2) not null check (per_acre_cost_pkr > 0),
  total_projected_pkr   numeric(16, 2) not null check (total_projected_pkr >= 0),
  created_at            timestamptz not null default now()
);
create unique index if not exists projected_costs_season_category_key
  on public.projected_costs (season_id, category);

alter table public.seasons enable row level security;
alter table public.expenses enable row level security;
alter table public.projected_costs enable row level security;

do $$ begin
  create policy "seasons_select_own" on public.seasons for select using (true);
  create policy "seasons_insert_own" on public.seasons for insert with check (true);
  create policy "seasons_update_own" on public.seasons for update using (true);
  create policy "seasons_delete_own" on public.seasons for delete using (true);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy "expenses_select_own" on public.expenses for select using (true);
  create policy "expenses_insert_own" on public.expenses for insert with check (true);
  create policy "expenses_update_own" on public.expenses for update using (true);
  create policy "expenses_delete_own" on public.expenses for delete using (true);
exception when duplicate_object then null; end $$;

do $$ begin
  create policy "projected_costs_select_own" on public.projected_costs for select using (true);
  create policy "projected_costs_insert_own" on public.projected_costs for insert with check (true);
  create policy "projected_costs_update_own" on public.projected_costs for update using (true);
  create policy "projected_costs_delete_own" on public.projected_costs for delete using (true);
exception when duplicate_object then null; end $$;
