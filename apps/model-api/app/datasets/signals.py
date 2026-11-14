from __future__ import annotations

import numpy as np
import pandas as pd

SEASON_MONTHS = {
    "rabi": (11, 12, 1, 2, 3, 4),
    "kharif": (5, 6, 7, 8, 9, 10),
    "annual": tuple(range(1, 13)),
}

# A season is only usable if nearly all of its days are present. Partial
# seasons at either edge of the record would otherwise bias trend estimates.
MIN_SEASON_COVERAGE = 0.85
EXPECTED_SEASON_DAYS = {
    "rabi": 181,
    "kharif": 184,
    "annual": 365,
}

BASELINE_START = 1981
BASELINE_END = 2010

HEAT_THRESHOLDS = (35.0, 40.0, 45.0)
HEAVY_RAIN_MM = 25.0
EXTREME_RAIN_MM = 50.0
WET_DAY_MM = 1.0
DRY_SPELL_THRESHOLD_MM = 1.0

SEASON_FEATURE_COLUMNS = [
    "tmean_c",
    "tmax_mean_c",
    "tmax_p95_c",
    "heat_days_35",
    "heat_days_40",
    "heat_days_45",
    "cooling_degree_days",
    "frost_days_min",
    "frost_days_reported",
    "frost_flag",
    "precip_total_mm",
    "precip_wet_days",
    "precip_cv",
    "precip_max_1d_mm",
    "precip_max_5d_mm",
    "heavy_rain_days",
    "extreme_rain_days",
    "dry_spell_max_days",
    "soil_moisture_top_mean",
    "soil_moisture_root_mean",
    "soil_moisture_profile_mean",
    "soil_moisture_profile_min",
    "soil_moisture_profile_p05",
    "evaporation_total_mm",
    "evaporation_energy_mj",
    "aridity_index",
    "rh_mean_pct",
    "solar_mean_mj",
    "wind_mean_ms",
    "ndvi_mean",
    "ndvi_min",
    "ndvi_stress_days",
]

INDICATOR_COLUMNS = [
    "temp_shift_c",
    "temp_shift_z",
    "heat_stress_index",
    "rainfall_anomaly_pct",
    "rainfall_reliability",
    "soil_moisture_anomaly",
    "evaporation_anomaly",
    "frost_risk_index",
    "extreme_precip_index",
    "vegetation_stress_index",
    "water_balance_mm",
]


def _slope(values: np.ndarray, years: np.ndarray) -> float:
    mask = np.isfinite(values) & np.isfinite(years)
    if mask.sum() < 3:
        return float("nan")
    x = years[mask].astype(float)
    y = values[mask].astype(float)
    x_centered = x - x.mean()
    denominator = float(np.dot(x_centered, x_centered))
    if denominator == 0.0:
        return float("nan")
    return float(np.dot(x_centered, y - y.mean()) / denominator)


def _max_dry_spell(precip: np.ndarray, threshold: float = DRY_SPELL_THRESHOLD_MM) -> float:
    if precip.size == 0:
        return 0.0
    dry = precip < threshold
    if not dry.any():
        return 0.0
    padded = np.concatenate(([False], dry, [False]))
    changes = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    return float((ends - starts).max()) if starts.size else 0.0


def _rolling_max(values: np.ndarray, window: int) -> float:
    if values.size == 0:
        return 0.0
    if values.size < window:
        return float(values.sum())
    sums = np.convolve(values, np.ones(window, dtype=float), mode="valid")
    return float(sums.max())


def _season_year(years: np.ndarray, months: np.ndarray, season: str) -> np.ndarray:
    if season == "rabi":
        # A rabi season is labelled by its harvest year: Nov-Dec belong to year+1.
        return np.where(months >= 11, years + 1, years)
    return years


def _safe_mean(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(finite.mean()) if finite.size else float("nan")


def _aggregate_season(
    values: dict[str, np.ndarray],
    season: str,
) -> pd.DataFrame:
    years = values["year"]
    months = values["month"]
    mask = np.isin(months, SEASON_MONTHS[season])
    if not mask.any():
        return pd.DataFrame()

    season_years = _season_year(years[mask], months[mask], season)

    rows: list[dict] = []
    for season_year in np.unique(season_years):
        sel = season_years == season_year
        index = np.flatnonzero(mask)[sel]
        expected = EXPECTED_SEASON_DAYS[season]
        if index.size < expected * MIN_SEASON_COVERAGE:
            continue

        tmax = values["t2m_max"][index]
        tmin = values["t2m_min"][index]
        tmean = values["t2m"][index]
        precip = values["prectotcorr"][index]
        sm_top = values["gwettop"][index]
        sm_root = values["gwetroot"][index]
        sm_prof = values["gwetprof"][index]
        evap = values["evland"][index]
        evap_energy = values["evptrns"][index]
        rh = values["rh2m"][index]
        solar = values["allsky_sfc_sw_dwn"][index]
        wind = values["ws2m"][index]
        frost_reported = values["frost_days"][index]
        cdd = values["cdd0"][index]
        ndvi = values.get("ndvi")

        rain_total = float(np.sum(precip))
        rain_mean = float(np.mean(precip))
        rain_std = float(np.std(precip))
        et_total = float(np.sum(evap))

        ndvi_mean = float("nan")
        ndvi_min = float("nan")
        ndvi_stress = float("nan")
        if ndvi is not None:
            window = ndvi[index]
            window = window[np.isfinite(window)]
            if window.size:
                ndvi_mean = float(np.mean(window))
                ndvi_min = float(np.min(window))
                ndvi_stress = float(np.sum(window < 0.25))

        rows.append(
            {
                "season": season,
                "year": int(season_year),
                "days_observed": int(index.size),
                "tmean_c": float(np.mean(tmean)),
                "tmax_mean_c": float(np.mean(tmax)),
                "tmax_p95_c": float(np.percentile(tmax, 95)),
                "heat_days_35": float(np.sum(tmax >= HEAT_THRESHOLDS[0])),
                "heat_days_40": float(np.sum(tmax >= HEAT_THRESHOLDS[1])),
                "heat_days_45": float(np.sum(tmax >= HEAT_THRESHOLDS[2])),
                "cooling_degree_days": float(np.sum(np.maximum(cdd, 0.0))),
                "frost_days_min": float(np.sum(tmin < 0.0)),
                "frost_days_reported": float(np.sum(frost_reported)),
                "frost_flag": float(np.any(tmin < 0.0)),
                "precip_total_mm": rain_total,
                "precip_wet_days": float(np.sum(precip >= WET_DAY_MM)),
                "precip_cv": float(rain_std / rain_mean) if rain_mean > 0 else 0.0,
                "precip_max_1d_mm": float(np.max(precip)),
                "precip_max_5d_mm": _rolling_max(precip, 5),
                "heavy_rain_days": float(np.sum(precip >= HEAVY_RAIN_MM)),
                "extreme_rain_days": float(np.sum(precip >= EXTREME_RAIN_MM)),
                "dry_spell_max_days": _max_dry_spell(precip),
                "soil_moisture_top_mean": float(np.mean(sm_top)),
                "soil_moisture_root_mean": float(np.mean(sm_root)),
                "soil_moisture_profile_mean": float(np.mean(sm_prof)),
                "soil_moisture_profile_min": float(np.min(sm_prof)),
                "soil_moisture_profile_p05": float(np.percentile(sm_prof, 5)),
                "evaporation_total_mm": et_total,
                "evaporation_energy_mj": float(np.sum(evap_energy)),
                "aridity_index": float(rain_total / et_total) if et_total > 0 else 0.0,
                "rh_mean_pct": float(np.mean(rh)),
                "solar_mean_mj": _safe_mean(solar),
                "wind_mean_ms": float(np.mean(wind)),
                "ndvi_mean": ndvi_mean,
                "ndvi_min": ndvi_min,
                "ndvi_stress_days": ndvi_stress,
            }
        )

    return pd.DataFrame(rows)


def seasonal_features(frame: pd.DataFrame, site: str) -> pd.DataFrame:
    values = {
        "year": frame.index.year.to_numpy(),
        "month": frame.index.month.to_numpy(),
        "t2m": frame["t2m"].to_numpy(dtype=float),
        "t2m_max": frame["t2m_max"].to_numpy(dtype=float),
        "t2m_min": frame["t2m_min"].to_numpy(dtype=float),
        "prectotcorr": frame["prectotcorr"].to_numpy(dtype=float),
        "rh2m": frame["rh2m"].to_numpy(dtype=float),
        "ws2m": frame["ws2m"].to_numpy(dtype=float),
        "allsky_sfc_sw_dwn": frame["allsky_sfc_sw_dwn"].to_numpy(dtype=float),
        "gwettop": frame["gwettop"].to_numpy(dtype=float),
        "gwetroot": frame["gwetroot"].to_numpy(dtype=float),
        "gwetprof": frame["gwetprof"].to_numpy(dtype=float),
        "evland": frame["evland"].to_numpy(dtype=float),
        "evptrns": frame["evptrns"].to_numpy(dtype=float),
        "frost_days": frame["frost_days"].to_numpy(dtype=float),
        "cdd0": frame["cdd0"].to_numpy(dtype=float),
    }
    if "ndvi" in frame.columns:
        values["ndvi"] = frame["ndvi"].to_numpy(dtype=float)

    parts = []
    for season in SEASON_MONTHS:
        aggregated = _aggregate_season(values, season)
        if not aggregated.empty:
            parts.append(aggregated)

    if not parts:
        return pd.DataFrame()

    seasonal = pd.concat(parts, ignore_index=True)
    seasonal.insert(0, "site", site)
    if "province" in frame.columns:
        seasonal.insert(1, "province", str(frame["province"].iloc[0]))
    if "latitude" in frame.columns:
        seasonal.insert(2, "latitude", float(frame["latitude"].iloc[0]))
        seasonal.insert(3, "longitude", float(frame["longitude"].iloc[0]))
    return seasonal


def add_indicators(seasonal: pd.DataFrame) -> pd.DataFrame:
    if seasonal.empty:
        return seasonal

    enriched = seasonal.copy()
    indicator_frames = []

    for (site, season), group in enriched.groupby(["site", "season"], sort=False):
        group = group.sort_values("year").copy()
        years = group["year"].to_numpy(dtype=float)
        baseline = group[
            (group["year"] >= BASELINE_START) & (group["year"] <= BASELINE_END)
        ]

        tmean_base = float(baseline["tmean_c"].mean()) if len(baseline) else float(
            group["tmean_c"].mean()
        )
        tmean_std = float(baseline["tmean_c"].std()) if len(baseline) > 1 else 1.0
        tmean_std = tmean_std if tmean_std > 0 else 1.0
        rain_base = float(baseline["precip_total_mm"].mean()) if len(baseline) else float(
            group["precip_total_mm"].mean()
        )
        soil_base = (
            float(baseline["soil_moisture_profile_mean"].mean())
            if len(baseline)
            else float(group["soil_moisture_profile_mean"].mean())
        )
        et_base = (
            float(baseline["evaporation_total_mm"].mean())
            if len(baseline)
            else float(group["evaporation_total_mm"].mean())
        )
        ndvi_base = (
            float(baseline["ndvi_mean"].mean())
            if len(baseline) and np.isfinite(baseline["ndvi_mean"]).any()
            else float("nan")
        )

        group["temp_shift_c"] = group["tmean_c"] - tmean_base
        group["temp_shift_z"] = group["temp_shift_c"] / tmean_std
        group["heat_stress_index"] = (
            group["heat_days_35"] * 1.0
            + group["heat_days_40"] * 2.0
            + group["heat_days_45"] * 3.0
        ) / group["days_observed"]
        group["rainfall_anomaly_pct"] = (
            (group["precip_total_mm"] - rain_base) / rain_base * 100.0
            if rain_base > 0
            else 0.0
        )
        group["rainfall_reliability"] = 1.0 / (1.0 + group["precip_cv"])
        group["soil_moisture_anomaly"] = (
            group["soil_moisture_profile_mean"] - soil_base
        )
        group["evaporation_anomaly"] = (
            group["evaporation_total_mm"] - et_base
        )
        group["frost_risk_index"] = (
            group["frost_days_min"] + group["frost_days_reported"]
        ) / group["days_observed"]
        group["extreme_precip_index"] = (
            group["heavy_rain_days"] + 2.0 * group["extreme_rain_days"]
        ) / group["days_observed"]
        group["water_balance_mm"] = (
            group["precip_total_mm"] - group["evaporation_total_mm"]
        )

        if np.isfinite(ndvi_base):
            group["vegetation_stress_index"] = (
                (ndvi_base - group["ndvi_mean"]) / ndvi_base
                if ndvi_base != 0
                else 0.0
            )
        else:
            # Proxy when no NDVI is available: heat + moisture deficit + aridity.
            heat = group["heat_stress_index"] / (group["heat_stress_index"].max() or 1.0)
            moisture = group["soil_moisture_anomaly"].clip(upper=0.0).abs()
            moisture = moisture / (moisture.max() or 1.0)
            aridity = (1.0 - group["aridity_index"].clip(0.0, 1.0))
            group["vegetation_stress_index"] = 0.45 * heat + 0.35 * moisture + 0.2 * aridity

        group["tmean_trend_c_per_decade"] = _slope(group["tmean_c"].to_numpy(), years) * 10.0
        group["precip_trend_mm_per_decade"] = (
            _slope(group["precip_total_mm"].to_numpy(), years) * 10.0
        )
        group["soil_moisture_trend_per_decade"] = (
            _slope(group["soil_moisture_profile_mean"].to_numpy(), years) * 10.0
        )

        indicator_frames.append(group)

    return pd.concat(indicator_frames, ignore_index=True)


def add_forecast_targets(seasonal: pd.DataFrame) -> pd.DataFrame:
    """Label each row with the following year's observed conditions.

    These are the supervised targets for the forecasting model: given this
    season's conditions, predict next season's heat, rain, moisture and stress.
    """
    if seasonal.empty:
        return seasonal

    target_map = {
        "tmean_c": "target_next_tmean_c",
        "heat_days_35": "target_next_heat_days_35",
        "precip_total_mm": "target_next_precip_total_mm",
        "soil_moisture_profile_mean": "target_next_soil_moisture",
        "frost_days_min": "target_next_frost_days",
        "extreme_rain_days": "target_next_extreme_rain_days",
        "vegetation_stress_index": "target_next_vegetation_stress",
    }

    frames = []
    for (site, season), group in seasonal.groupby(["site", "season"], sort=False):
        group = group.sort_values("year").copy()
        for source, target in target_map.items():
            if source in group.columns:
                group[target] = group[source].shift(-1)
        frames.append(group)

    labelled = pd.concat(frames, ignore_index=True)
    target_columns = [column for column in target_map.values() if column in labelled.columns]
    if target_columns:
        labelled = labelled.dropna(subset=target_columns, how="all")
    return labelled.reset_index(drop=True)


def long_term_trends(seasonal: pd.DataFrame) -> pd.DataFrame:
    if seasonal.empty:
        return pd.DataFrame()

    rows = []
    for (site, season), group in seasonal.groupby(["site", "season"], sort=False):
        group = group.sort_values("year")
        years = group["year"].to_numpy(dtype=float)
        if len(group) < 5:
            continue

        first_decade = group[group["year"] < 1991]
        last_decade = group[group["year"] >= 2015]

        def _delta(column: str) -> float:
            if column not in group.columns or first_decade.empty or last_decade.empty:
                return float("nan")
            early = float(first_decade[column].mean())
            late = float(last_decade[column].mean())
            return late - early

        rows.append(
            {
                "site": site,
                "province": group["province"].iloc[0]
                if "province" in group.columns
                else None,
                "season": season,
                "years_observed": int(len(group)),
                "tmean_c_per_decade": _slope(
                    group["tmean_c"].to_numpy(dtype=float), years
                )
                * 10.0,
                "heat_days_35_per_decade": _slope(
                    group["heat_days_35"].to_numpy(dtype=float), years
                )
                * 10.0,
                "precip_mm_per_decade": _slope(
                    group["precip_total_mm"].to_numpy(dtype=float), years
                )
                * 10.0,
                "soil_moisture_per_decade": _slope(
                    group["soil_moisture_profile_mean"].to_numpy(dtype=float), years
                )
                * 10.0,
                "frost_days_per_decade": _slope(
                    group["frost_days_min"].to_numpy(dtype=float), years
                )
                * 10.0,
                "tmean_delta_1980s_to_2010s": _delta("tmean_c"),
                "precip_delta_1980s_to_2010s": _delta("precip_total_mm"),
                "soil_moisture_delta_1980s_to_2010s": _delta(
                    "soil_moisture_profile_mean"
                ),
            }
        )

    return pd.DataFrame(rows)
