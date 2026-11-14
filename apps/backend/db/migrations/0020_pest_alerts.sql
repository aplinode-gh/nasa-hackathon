-- 0020 — Pest risk forecasts and alerts.

create table if not exists public.pest_alerts (
  id                  uuid primary key default gen_random_uuid(),
  account_id          uuid not null references public.users(id) on delete cascade,
  farm_id             uuid not null references public.farms(id) on delete cascade,
  crop                text,
  pest_type           text not null,
  risk_score          integer not null default 0 check (risk_score >= 0 and risk_score <= 100),
  severity            text not null default 'warning' check (severity in ('warning','critical')),
  recommendation_text text not null default '',
  status              text not null default 'active' check (status in ('active','monitoring')),
  created_at          timestamptz not null default now(),
  read_at             timestamptz
);
create index if not exists pest_alerts_account_idx
  on public.pest_alerts (account_id, created_at desc);
create index if not exists pest_alerts_farm_idx
  on public.pest_alerts (farm_id, created_at desc);

alter table public.pest_alerts enable row level security;

do $$ begin
  create policy "pest_alerts_select_own" on public.pest_alerts for select using (true);
  create policy "pest_alerts_insert_own" on public.pest_alerts for insert with check (true);
  create policy "pest_alerts_update_own" on public.pest_alerts for update using (true);
  create policy "pest_alerts_delete_own" on public.pest_alerts for delete using (true);
exception when duplicate_object then null; end $$;
