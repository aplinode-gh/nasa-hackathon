-- 0021 — Align crop recommendation tables with the existing crops schema.
-- The deployed `crops` table (0008) uses varchar ids and multilingual names.
-- 0009 assumed a fresh uuid-based table, so it could not be applied. This
-- migration adds the recommendation columns to the existing table, creates
-- the supporting reference/transactional tables with matching key types, and
-- seeds the catalogue.

alter table public.crops
  add column if not exists name_key text,
  add column if not exists typical_yield_per_acre_kg numeric(8,2) not null default 0,
  add column if not exists growing_duration_days integer not null default 120,
  add column if not exists season_windows text[] not null default '{}'::text[],
  add column if not exists water_requirement_level text not null default 'medium',
  add column if not exists labour_cost_level text not null default 'medium',
  add column if not exists capital_requirement_per_acre_pkr numeric(12,2) not null default 0,
  add column if not exists market_risk_baseline text not null default 'medium',
  add column if not exists notes text,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists crops_name_en_lower_key on public.crops (lower(name_en));

insert into public.crops (
  id, name_en, name_ur, name_pa, name_ps, name_sd, name_skr, name_bal, name_hno,
  category, unit, name_key, typical_yield_per_acre_kg, growing_duration_days,
  season_windows, water_requirement_level, labour_cost_level,
  capital_requirement_per_acre_pkr, market_risk_baseline, notes
)
select
  v.id, v.name_en, v.name_en, v.name_en, v.name_en, v.name_en, v.name_en, v.name_en, v.name_en,
  v.category, 'Maund', 'app.crops.catalogue.' || replace(v.id, ' ', '_'), v.yield_kg, v.days,
  v.seasons, v.water, v.labour, v.capital, v.risk, v.notes
from (values
  ('wheat','Wheat','staple',800,120,array['winter'],'medium','medium',18000,'low','Rabi staple across Punjab and Sindh.'),
  ('rice','Rice','staple',1200,150,array['rainy','summer'],'high','high',75000,'medium','Kharif staple; water-intensive.'),
  ('maize','Maize','staple',1600,110,array['summer','spring'],'medium','medium',22000,'low','Spring/summer cereal.'),
  ('sugarcane','Sugarcane','staple',35000,330,array['spring','summer'],'high','high',130000,'medium','Long-duration cash crop.'),
  ('cotton','Cotton','cash',600,160,array['summer','rainy'],'medium','high',55000,'high','Major kharif cash crop.'),
  ('gram','Gram','pulse',350,130,array['winter'],'low','low',15000,'low','Rabbi pulse; fixes nitrogen.'),
  ('mustard','Mustard','cash',400,125,array['winter'],'low','low',16000,'low','Oilseed; low water need.'),
  ('mung bean','Mung Bean','pulse',300,75,array['summer','rainy'],'low','low',14000,'low','Short-duration pulse; nitrogen-fixing.'),
  ('soybean','Soybean','pulse',450,110,array['summer','rainy'],'medium','medium',20000,'medium','Pulse with good market demand.'),
  ('potato','Potato','vegetable',9000,90,array['winter','autumn'],'medium','high',70000,'medium','Vegetable; high value per acre.'),
  ('onion','Onion','vegetable',6000,100,array['autumn','winter'],'medium','high',45000,'high','Vegetable; price volatile.'),
  ('tomato','Tomato','vegetable',9000,110,array['winter','spring','autumn'],'high','high',65000,'high','Vegetable; high value, pest pressure.'),
  ('barley','Barley','staple',1200,120,array['winter','autumn'],'low','low',12000,'low','Dryland cereal; drought-tolerant.'),
  ('millet','Millet','staple',800,90,array['summer','rainy'],'low','low',10000,'low','Pearl millet; arid-zone staple.'),
  ('sorghum','Sorghum','staple',1000,100,array['summer','rainy'],'low','low',11000,'low','Drought-tolerant cereal.'),
  ('sunflower','Sunflower','cash',800,90,array['spring','summer','autumn'],'low','low',18000,'medium','Oilseed; short duration.'),
  ('sesame','Sesame','cash',300,90,array['summer','spring'],'low','low',12000,'medium','Drought-tolerant oilseed.'),
  ('lentil','Lentil','pulse',400,120,array['winter'],'low','low',14000,'low','Short-duration pulse.'),
  ('peanut','Peanut','cash',500,120,array['summer','rainy'],'low','medium',25000,'medium','Groundnut; warm-season oilseed.'),
  ('cauliflower','Cauliflower','vegetable',8000,100,array['winter','autumn'],'medium','high',50000,'medium','Cool-season vegetable.'),
  ('cabbage','Cabbage','vegetable',7000,95,array['winter','autumn'],'medium','high',48000,'medium','Cool-season vegetable.'),
  ('carrot','Carrot','vegetable',5000,70,array['winter','autumn'],'medium','medium',35000,'medium','Cool-season root.'),
  ('radish','Radish','vegetable',5000,60,array['winter','autumn'],'low','medium',22000,'low','Cool-season root.'),
  ('spinach','Spinach','vegetable',4000,45,array['winter','autumn'],'low','medium',15000,'low','Cool-season leafy green.'),
  ('okra','Okra','vegetable',4000,60,array['summer','rainy'],'medium','medium',30000,'medium','Short-duration vegetable.'),
  ('chili','Chili','vegetable',2000,120,array['summer','rainy'],'medium','high',40000,'high','Hot pepper; high value.'),
  ('cucumber','Cucumber','vegetable',6000,55,array['summer','spring'],'high','medium',25000,'medium','Short-duration vegetable.'),
  ('watermelon','Watermelon','vegetable',8000,90,array['summer','rainy'],'high','medium',30000,'medium','Warm-season fruit/vegetable.'),
  ('muskmelon','Muskmelon','vegetable',7000,85,array['summer','rainy'],'high','medium',28000,'medium','Warm-season vine crop.'),
  ('citrus','Citrus','cash',10000,365,array['winter','spring'],'medium','medium',70000,'medium','Perennial fruit; medium-term.'),
  ('mango','Mango','cash',8000,365,array['spring','summer'],'medium','medium',80000,'medium','Perennial fruit; long-term.'),
  ('banana','Banana','cash',12000,365,array['summer','spring'],'high','medium',90000,'medium','Perennial fruit; high water need.'),
  ('apple','Apple','cash',12000,365,array['spring','summer'],'medium','high',80000,'medium','Temperate fruit; high-input.'),
  ('grape','Grape','cash',9000,365,array['spring','summer'],'medium','high',85000,'medium','Perennial fruit; trellis system.'),
  ('olive','Olive','cash',3000,365,array['winter','spring'],'low','medium',60000,'medium','Drought-tolerant perennial oil crop.'),
  ('date palm','Date Palm','cash',6000,365,array['summer','spring'],'high','medium',70000,'medium','Arid-zone perennial fruit.')
) as v(id, name_en, category, yield_kg, days, seasons, water, labour, capital, risk, notes)
on conflict (id) do update set
  name_en = excluded.name_en,
  category = excluded.category,
  name_key = excluded.name_key,
  typical_yield_per_acre_kg = excluded.typical_yield_per_acre_kg,
  growing_duration_days = excluded.growing_duration_days,
  season_windows = excluded.season_windows,
  water_requirement_level = excluded.water_requirement_level,
  labour_cost_level = excluded.labour_cost_level,
  capital_requirement_per_acre_pkr = excluded.capital_requirement_per_acre_pkr,
  market_risk_baseline = excluded.market_risk_baseline,
  notes = excluded.notes,
  updated_at = now();

create table if not exists public.crop_soil_compatibility (
  id                uuid primary key default gen_random_uuid(),
  crop_id           varchar(64) not null references public.crops(id) on delete cascade,
  soil_type         text not null check (soil_type in ('sandy','sandy_loam','loamy','clay_loam','clay','silty','saline','rocky','other')),
  suitability_score numeric(4,3) not null check (suitability_score >= 0 and suitability_score <= 1),
  ph_min            numeric(3,1),
  ph_max            numeric(3,1),
  notes             text
);
create unique index if not exists crop_soil_crop_soil_key on public.crop_soil_compatibility (crop_id, soil_type);
create index if not exists crop_soil_crop_idx on public.crop_soil_compatibility (crop_id);

create table if not exists public.crop_rotation_rules (
  id                 uuid primary key default gen_random_uuid(),
  previous_crop_id   varchar(64) not null references public.crops(id) on delete cascade,
  next_crop_id       varchar(64) not null references public.crops(id) on delete cascade,
  benefit            text not null,
  reason_key         text not null,
  suitability_score  numeric(4,3) not null check (suitability_score >= 0 and suitability_score <= 1)
);
create unique index if not exists crop_rotation_prev_next_key on public.crop_rotation_rules (previous_crop_id, next_crop_id);
create index if not exists crop_rotation_prev_idx on public.crop_rotation_rules (previous_crop_id);

create table if not exists public.soil_profiles (
  id                    uuid primary key default gen_random_uuid(),
  district              text not null,
  province              text not null,
  dominant_soil_type    text not null,
  secondary_soil_type   text,
  ph_typical            numeric(3,1),
  organic_matter_band   text check (organic_matter_band in ('low','medium','high')),
  notes                 text,
  created_at            timestamptz not null default now()
);
create unique index if not exists soil_profiles_district_province_key on public.soil_profiles (district, province);

create table if not exists public.crop_price_trends (
  id                    uuid primary key default gen_random_uuid(),
  crop_id               varchar(64) not null references public.crops(id) on delete cascade,
  observed_at           date not null,
  price_per_maan_pkr    numeric(10,2) not null,
  trend                 text not null default 'stable' check (trend in ('up','stable','down')),
  volatility            numeric(4,3) not null default 0.100 check (volatility >= 0 and volatility <= 1)
);
create index if not exists crop_price_trends_crop_date_idx on public.crop_price_trends (crop_id, observed_at desc);

create table if not exists public.crop_recommendation_requests (
  id                        uuid primary key default gen_random_uuid(),
  account_id                uuid not null references public.users(id) on delete cascade,
  farm_id                   uuid not null references public.farms(id) on delete cascade,
  target_season             text not null,
  target_year               integer not null,
  soil_type                 text not null,
  soil_is_regional_default  boolean not null default false,
  irrigation_type           text not null,
  budget_bracket            text not null,
  weather_confidence        text not null default 'full',
  market_confidence         text not null default 'full',
  soil_confidence           text not null default 'full',
  inputs_snapshot           jsonb not null default '{}'::jsonb,
  created_at                timestamptz not null default now()
);
create unique index if not exists crop_rec_requests_account_farm_season_year_key
  on public.crop_recommendation_requests (account_id, farm_id, target_season, target_year);
create index if not exists crop_rec_requests_account_idx
  on public.crop_recommendation_requests (account_id, created_at desc);

create table if not exists public.crop_recommendations (
  id                            uuid primary key default gen_random_uuid(),
  request_id                    uuid not null references public.crop_recommendation_requests(id) on delete cascade,
  rank                          integer not null check (rank in (1,2,3)),
  crop_id                       varchar(64) not null references public.crops(id),
  expected_revenue_per_acre_pkr numeric(12,2) not null,
  revenue_confidence            text not null default 'medium',
  reason_key                    text not null,
  risk_factors                  text[] not null default '{}',
  water_requirement_level       text not null,
  suitability_score             numeric(4,3) not null,
  weather_fit_score             numeric(4,3) not null,
  profitability_score           numeric(4,3) not null,
  risk_score                    numeric(4,3) not null,
  sustainability_score          numeric(4,3) not null,
  final_score                   numeric(4,3) not null,
  data_sources_used             text[] not null default '{}',
  data_fresheness_seconds       integer not null default 0,
  created_at                    timestamptz not null default now()
);
create unique index if not exists crop_recs_request_rank_key on public.crop_recommendations (request_id, rank);
create index if not exists crop_recs_request_idx on public.crop_recommendations (request_id);

create table if not exists public.farm_plan_entries (
  id                 uuid primary key default gen_random_uuid(),
  account_id         uuid not null references public.users(id) on delete cascade,
  farm_id            uuid not null references public.farms(id) on delete cascade,
  recommendation_id  uuid not null references public.crop_recommendations(id) on delete cascade,
  target_season      text not null,
  target_year        integer not null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create unique index if not exists farm_plan_farm_season_year_key
  on public.farm_plan_entries (farm_id, target_season, target_year);

create table if not exists public.crop_rotation_suggestions (
  id                  uuid primary key default gen_random_uuid(),
  farm_plan_entry_id  uuid not null references public.farm_plan_entries(id) on delete cascade,
  sequence_position   integer not null check (sequence_position in (1,2,3)),
  target_season       text not null,
  target_year         integer not null,
  crop_id             varchar(64) not null references public.crops(id),
  reason_key          text not null,
  is_generic          boolean not null default false,
  created_at          timestamptz not null default now()
);
create unique index if not exists rotation_suggestions_entry_seq_key
  on public.crop_rotation_suggestions (farm_plan_entry_id, sequence_position);

insert into public.crop_soil_compatibility (crop_id, soil_type, suitability_score, ph_min, ph_max, notes)
select c.id, s.soil, sc.score, s.ph_min, s.ph_max, sc.note
from public.crops c
cross join (values
  ('loamy',1.00,6.0,7.5),('sandy_loam',0.90,6.0,7.5),('clay_loam',0.85,6.0,7.8),
  ('silty',0.80,6.2,7.6),('sandy',0.65,6.0,7.5),('clay',0.70,6.0,8.0),
  ('saline',0.45,7.0,8.5),('rocky',0.35,6.0,7.5),('other',0.70,6.0,7.5)
) as s(soil, score, ph_min, ph_max)
cross join lateral (
  select
    case
      when c.id in ('rice','sugarcane') then
        case s.soil when 'clay' then 0.95 when 'clay_loam' then 0.90 when 'loamy' then 0.80
                     when 'silty' then 0.75 when 'sandy_loam' then 0.70 when 'sandy' then 0.40
                     when 'saline' then 0.30 when 'rocky' then 0.20 else 0.70 end
      when c.category = 'pulse' then
        case s.soil when 'sandy_loam' then 0.95 when 'loamy' then 0.90 when 'sandy' then 0.85
                     when 'clay_loam' then 0.80 when 'silty' then 0.78 when 'clay' then 0.70
                     when 'saline' then 0.50 when 'rocky' then 0.40 else 0.80 end
      when c.category = 'vegetable' then
        case s.soil when 'loamy' then 0.95 when 'sandy_loam' then 0.90 when 'silty' then 0.88
                     when 'clay_loam' then 0.82 when 'sandy' then 0.60 when 'clay' then 0.65
                     when 'saline' then 0.40 when 'rocky' then 0.25 else 0.75 end
      else
        case s.soil when 'loamy' then 1.00 when 'sandy_loam' then 0.92 when 'clay_loam' then 0.85
                     when 'silty' then 0.82 when 'clay' then 0.72 when 'sandy' then 0.68
                     when 'saline' then 0.45 when 'rocky' then 0.35 else 0.72 end
    end as score,
    case
      when c.id in ('rice','sugarcane') then 'Prefers heavy, water-retentive soils.'
      when c.category = 'pulse' then 'Thrives on well-drained light soils; fixes nitrogen.'
      when c.category = 'vegetable' then 'Needs fertile, well-drained loamy soils.'
      else 'Adapted to fertile loamy and clay-loam plains.'
    end as note
) as sc
on conflict (crop_id, soil_type) do nothing;

insert into public.crop_rotation_rules (previous_crop_id, next_crop_id, benefit, reason_key, suitability_score)
select r.prev, r.next, r.benefit, r.reason_key, r.score
from (values
  ('wheat','mung bean','Nitrogen fixation after cereal','app.crops.rotation.wheat_then_mung',0.92),
  ('wheat','gram','Legume builds soil after wheat','app.crops.rotation.wheat_then_gram',0.88),
  ('wheat','cotton','Common Punjab follow-on','app.crops.rotation.wheat_then_cotton',0.70),
  ('cotton','wheat','Cereal restores after cotton','app.crops.rotation.cotton_then_wheat',0.85),
  ('cotton','maize','Maize follows cotton on good land','app.crops.rotation.cotton_then_maize',0.72),
  ('rice','wheat','Classic kharif to rabi sequence','app.crops.rotation.rice_then_wheat',0.90),
  ('rice','maize','Maize after paddy on residual moisture','app.crops.rotation.rice_then_maize',0.78),
  ('maize','potato','Potato after maize on loam','app.crops.rotation.maize_then_potato',0.80),
  ('maize','wheat','Wheat after maize','app.crops.rotation.maize_then_wheat',0.82),
  ('potato','maize','Maize follows potato','app.crops.rotation.potato_then_maize',0.76),
  ('sugarcane','maize','Maize after ratoon cane','app.crops.rotation.sugarcane_then_maize',0.74),
  ('mung bean','wheat','Cereal after pulse','app.crops.rotation.mung_then_wheat',0.86),
  ('gram','cotton','Cotton after legume','app.crops.rotation.gram_then_cotton',0.80),
  ('mustard','cotton','Cotton after oilseed','app.crops.rotation.mustard_then_cotton',0.70),
  ('soybean','wheat','Wheat after soybean','app.crops.rotation.soybean_then_wheat',0.84),
  ('onion','maize','Maize after onion on fertile bed','app.crops.rotation.onion_then_maize',0.75),
  ('tomato','wheat','Wheat after tomato','app.crops.rotation.tomato_then_wheat',0.73),
  ('barley','gram','Pulse after barley breaks cereal cycle','app.crops.rotation.barley_then_gram',0.72),
  ('millet','mung bean','Mung bean after millet on sandy loam','app.crops.rotation.millet_then_mung',0.68),
  ('sunflower','wheat','Wheat after sunflower on good land','app.crops.rotation.sunflower_then_wheat',0.70),
  ('lentil','cotton','Cotton after lentil benefits from nitrogen','app.crops.rotation.lentil_then_cotton',0.74)
) as r(prev, next, benefit, reason_key, score)
where exists (select 1 from public.crops a where a.id = r.prev)
  and exists (select 1 from public.crops b where b.id = r.next)
on conflict (previous_crop_id, next_crop_id) do nothing;

insert into public.soil_profiles (district, province, dominant_soil_type, secondary_soil_type, ph_typical, organic_matter_band, notes)
values
  ('Multan','Punjab','loamy','clay_loam',7.6,'medium','Indus plains, productive.'),
  ('Faisalabad','Punjab','clay_loam','loamy',7.8,'medium','Canal-irrigated loams.'),
  ('Sahiwal','Punjab','loamy','sandy_loam',7.5,'medium','Mixed loams.'),
  ('Bahawalpur','Punjab','sandy','sandy_loam',7.9,'low','Desert margin sands.'),
  ('Lodhran','Punjab','sandy_loam','loamy',7.7,'low','Sandy loams.'),
  ('Rahim Yar Khan','Punjab','sandy','loamy',8.0,'low','Sandy, saline patches.'),
  ('Vehari','Punjab','clay_loam','loamy',7.8,'medium','Cotton belt clays.'),
  ('Lahore','Punjab','loamy','silty',7.5,'medium','Urban-peri loams.'),
  ('Sargodha','Punjab','loamy','silty',7.6,'medium','Citrus belt loams.'),
  ('Dera Ghazi Khan','Punjab','sandy','rocky',8.0,'low','Western arid sands.'),
  ('Hyderabad','Sindh','clay','clay_loam',7.9,'medium','Sindh clays.'),
  ('Sukkur','Sindh','clay','saline',8.1,'low','Saline clays.'),
  ('Larkana','Sindh','clay','loamy',7.9,'medium','Rice belt clays.'),
  ('Peshawar','Khyber Pakhtunkhwa','loamy','silty',7.3,'medium','Valley loams.'),
  ('Quetta','Balochistan','sandy_loam','rocky',7.6,'low','Arid loams, rocky.'),
  ('Nowshera','Khyber Pakhtunkhwa','loamy','silty',7.4,'medium','Valley alluvium.')
on conflict (district, province) do nothing;

insert into public.crop_price_trends (crop_id, observed_at, price_per_maan_pkr, trend, volatility)
select v.crop_id, current_date - 30, v.price, v.trend, v.vol
from (values
  ('wheat',3400,'up',0.12),('rice',4200,'stable',0.15),('maize',2600,'up',0.18),
  ('sugarcane',900,'stable',0.10),('cotton',7200,'down',0.28),('gram',6200,'stable',0.16),
  ('mustard',4200,'up',0.14),('mung bean',4800,'stable',0.20),('soybean',4000,'up',0.22),
  ('potato',2600,'down',0.35),('onion',5200,'down',0.45),('tomato',3800,'down',0.40)
) as v(crop_id, price, trend, vol)
where exists (select 1 from public.crops c where c.id = v.crop_id)
  and not exists (select 1 from public.crop_price_trends t where t.crop_id = v.crop_id);
