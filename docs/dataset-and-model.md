# Pakistan Climate Dataset & Forecast Model

This is the data and machine-learning side of the Agropioo / NASA Space Apps
"Field Shift" entry. It collects NASA Earth observations for 24 agricultural
sites across Pakistan, cleans them, engineers the indicators the challenge asks
for, and trains models that answer questions about next-season conditions.

The API lives in `apps/model-api` and is served by FastAPI alongside the
existing crop-rotation endpoints.

---

## What is in the dataset

| Property | Value |
| --- | --- |
| Source | NASA POWER daily point API (MERRA-2 reanalysis), community `AG` |
| Sites | 24 across all 7 regions (Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Islamabad, Gilgit-Baltistan, Azad Kashmir) |
| Period | 1981-01-01 to 2024-12-31 (44 years) |
| Daily rows | 385,704 (16,071 per site) |
| Raw variables | 20 |
| Season-years | 3,144 (rabi / kharif / annual per site) |
| Model features | 43 |
| Forecast targets | 7 |

Raw variables cover temperature (`t2m`, `t2m_max`, `t2m_min`, `t2m_range`),
humidity and dew point (`rh2m`, `t2mdew`, `qv2m`), rainfall (`prectotcorr`),
wind (`ws2m`, `ws2m_max`, `wd2m`), radiation (`allsky_sfc_sw_dwn`), surface and
root-zone soil wetness (`gwettop`, `gwetroot`, `gwetprof`), evaporation and its
energy flux (`evland`, `evptrns`), plus `frost_days` and `cdd0`.

## The nine indicators

The challenge lists nine signals. Each maps to derived columns:

| Indicator | Columns |
| --- | --- |
| Temperature shift | `tmean_c`, `temp_shift_c`, `temp_shift_z`, `tmean_c_per_decade` |
| Heat stress | `heat_days_35/40/45`, `heat_stress_index`, `cooling_degree_days` |
| Rainfall | `precip_total_mm`, `precip_cv`, `rainfall_anomaly_pct`, `rainfall_reliability` |
| Soil moisture | `soil_moisture_top/root/profile_mean`, `soil_moisture_profile_min/p05`, `soil_moisture_anomaly` |
| Evaporation | `evaporation_total_mm`, `evaporation_energy_mj`, `evaporation_anomaly`, `aridity_index` |
| Frost risk | `frost_days_min`, `frost_days_reported`, `frost_risk_index` |
| Extreme precipitation | `heavy_rain_days`, `extreme_rain_days`, `precip_max_1d/5d_mm`, `extreme_precip_index` |
| Vegetation stress | `vegetation_stress_index` (see caveat below) |
| Long-term water trends | `water_balance_mm`, `soil_moisture_per_decade`, `precip_mm_per_decade` |

### Vegetation stress caveat

`vegetation_stress_index` is currently a **meteorological proxy** built from
heat, soil-moisture deficit and aridity, because MODIS NDVI is not part of this
build. An NDVI ingester exists in `app/ingest/modis.py` (ORNL MODIS subset
service, MOD13Q1 250 m, 16-day composites), but that endpoint is severely rate
limited: roughly 4-5 minutes per site-year, and it rejects windows longer than
10 composite tiles. Ingesting 24 sites x 25 years is not practical in a
hackathon window, so NDVI is opt-in rather than default.

## Data quality handling

`app/datasets/clean.py` documents every correction it makes:

- POWER fill values (`-999`) become NaN before anything else.
- Physically impossible values are clipped to unit bounds (humidity to 0-100,
  precipitation and wind to >= 0, soil wetness to 0-1) and counted in the report.
- Inverted `t2m_max`/`t2m_min` pairs are swapped; `t2m` is clamped between them;
  soil wetness is ordered `top <= root <= profile`; wind gusts are forced above
  the mean wind.
- Gaps of up to 3 days are interpolated. **Longer gaps stay NaN.** This matters
  for `allsky_sfc_sw_dwn`, which POWER does not provide before 1984 — the
  pipeline reports those 1,089 missing days per site rather than inventing them.
- Duplicate dates are dropped and the index is completed to a regular daily grid.

Per-site results land in `artifacts/clean/clean_report.csv`.

## Seasons

- **rabi** (Nov-Apr), labelled by harvest year, so Nov-Dec 2024 belongs to rabi 2025.
- **kharif** (May-Oct).
- **annual** (Jan-Dec).

A season is only kept if at least 85% of its days are present, which drops
partial seasons at the edges of the record.

## Model

Seven quantile XGBoost regressors (p10/p50/p90) per target, trained on
next-season labels (`target_next_*`): mean temperature, heat days above 35 C,
seasonal rainfall, profile soil moisture, frost days, extreme rainfall days and
vegetation stress.

- **Split**: train < 2014, calibration 2014-2017, holdout >= 2018.
- **Location features**: latitude, longitude and a season one-hot are part of
  the design matrix, so one global model still answers location-specific questions.
- **Intervals**: raw quantile bands under-cover, so they are widened with
  conformalized quantile regression (CQR) calibrated on the 2014-2017 slice.
  Both raw and calibrated coverage are reported in `metrics.json`.

### Holdout performance (2018-2023)

| Target | R2 | MAE | vs persistence | 80% coverage (raw / calibrated) |
| --- | --- | --- | --- | --- |
| Mean temperature | 0.984 | 0.84 C | +11% | 0.43 / 0.56 |
| Heat days > 35 C | 0.889 | 15.6 days | +2% | 0.55 / 0.54 |
| Seasonal rainfall | 0.284 | 256 mm | +4% | 0.34 / 0.35 |
| Profile soil moisture | 0.530 | 0.060 | **-26%** | 0.32 / 0.32 |
| Frost days | 0.926 | 3.27 days | **-79%** | 0.76 / 0.64 |
| Extreme rain days | -0.139 | 1.01 days | +29% | 0.51 / 0.46 |
| Vegetation stress | -0.126 | 0.117 | -1% | 0.42 / 0.61 |

Read this honestly:

- Temperature and heat-day forecasts are genuinely useful.
- Rainfall and extreme-rain forecasts beat persistence but are still coarse;
  report them as ranges, not point estimates.
- **Soil moisture and frost do not beat persistence.** The API says so in its
  answers instead of pretending otherwise.
- Interval coverage is below the nominal 80%. The bands are an honest
  uncertainty signal, not a calibrated 80% guarantee.

## Running it

```sh
cd apps/model-api

# 1. Harvest NASA POWER for all 24 sites, 1981-2024 (~2 minutes)
npx nx run model-api:harvest --args="--sites all"

# 2. Clean + engineer indicators, write numpy arrays and parquet
npx nx run model-api:prepare --args="--sites all"

# 3. Train quantile forecasters
npx nx run model-api:train-forecast

# Or all three:
npx nx run model-api:pipeline

# Serve the API (port 8000)
npx nx run model-api:serve
```

Tests: `npx nx run model-api:test`.

## Outputs

```
datasets/power/<site>.csv        raw daily POWER data (gitignored)
artifacts/clean/
  cleaned/<site>.parquet         cleaned daily series
  seasonal_features.parquet      season-year indicators (includes newest season)
  training_table.parquet         rows with next-season targets
  X_features.npy                 (3072, 43) float32 feature matrix
  y_targets.npy                  (3072, 7)  float32 target matrix
  meta.npy                       site / province / season / year
  feature_names.json
  target_names.json
  long_term_trends.csv
  clean_report.csv
  summary.json
artifacts/models/
  <target>_q10|q50|q90.json      25 XGBoost models
  metrics.json, feature_spec.json, target_spec.json, calibration.json
```

`artifacts/` is gitignored; rebuild it with the commands above.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /sites` | All 24 sites with province and coordinates |
| `GET /forecast/{site}?season=rabi` | Current conditions, next-season bands, long-term trends |
| `POST /ask` | `{site, season, question}` — returns findings, caveats and the underlying numbers |

The `/ask` endpoint is deterministic retrieval over the trained model, not an
LLM call: it detects which of the nine signals a question mentions, pulls the
relevant forecast bands and trends, and explains them. Areas it cannot support
are stated as caveats.
