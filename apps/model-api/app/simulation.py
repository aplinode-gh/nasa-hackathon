from __future__ import annotations

import numpy as np

SOLAR_CONSTANT = 0.0820


def extraterrestrial_radiation_mm(
    lat_deg: float, day_of_year: np.ndarray
) -> np.ndarray:
    phi = np.radians(lat_deg)
    doy = np.asarray(day_of_year, dtype=float)
    inverse_distance = 1.0 + 0.033 * np.cos(2.0 * np.pi / 365.0 * doy)
    declination = 0.409 * np.sin(2.0 * np.pi / 365.0 * doy - 1.39)
    sunset_angle = np.arccos(
        np.clip(-np.tan(phi) * np.tan(declination), -1.0, 1.0)
    )
    ra_mj = (24.0 * 60.0 / np.pi) * SOLAR_CONSTANT * inverse_distance * (
        sunset_angle * np.sin(phi) * np.sin(declination)
        + np.cos(phi) * np.cos(declination) * np.sin(sunset_angle)
    )
    return np.maximum(ra_mj * 0.408, 0.0)


def et0_hargreaves(
    tmax_c: np.ndarray,
    tmin_c: np.ndarray,
    lat_deg: float,
    day_of_year: np.ndarray,
) -> np.ndarray:
    tmax = np.asarray(tmax_c, dtype=float)
    tmin = np.asarray(tmin_c, dtype=float)
    tmean = (tmax + tmin) / 2.0
    diurnal = np.maximum(tmax - tmin, 0.0)
    ra = extraterrestrial_radiation_mm(lat_deg, day_of_year)
    et0 = 0.0023 * (tmean + 17.8) * np.sqrt(diurnal) * ra
    return np.maximum(et0, 0.0)


def kc_curve(
    total_days: int, kc_ini: float, kc_mid: float, kc_end: float
) -> np.ndarray:
    init = max(int(round(total_days * 0.15)), 1)
    development = max(int(round(total_days * 0.25)), 1)
    late = max(int(round(total_days * 0.15)), 1)
    mid = max(total_days - init - development - late, 1)
    segments = [
        np.full(init, kc_ini, dtype=float),
        np.linspace(kc_ini, kc_mid, development, dtype=float),
        np.full(mid, kc_mid, dtype=float),
        np.linspace(kc_mid, kc_end, late, dtype=float),
    ]
    return np.concatenate(segments)[:total_days]


def total_available_water_mm(soil: dict, root_depth_m: float) -> float:
    available_water_capacity = 0.10 + 0.15 * float(soil["water_holding_capacity"])
    return available_water_capacity * root_depth_m * 1000.0


def simulate_season(
    precip_mm: np.ndarray,
    et0_mm: np.ndarray,
    kc: np.ndarray,
    taw_mm: float,
    depletion_fraction: float = 0.5,
    initial_depletion_mm: float = 0.0,
    irrigation_efficiency: float = 0.8,
    allow_irrigation: bool = True,
    ky: float = 1.0,
) -> dict[str, float]:
    precip = np.asarray(precip_mm, dtype=float)
    et0 = np.asarray(et0_mm, dtype=float)
    kc = np.asarray(kc, dtype=float)
    days = precip.size

    raw = depletion_fraction * taw_mm
    depletion = float(np.clip(initial_depletion_mm, 0.0, taw_mm))
    stress_days = 0
    irrigation_mm = 0.0
    crop_et_sum = 0.0
    actual_et_sum = 0.0

    for day in range(days):
        crop_et = float(kc[day] * et0[day])
        crop_et_sum += crop_et

        if depletion <= raw:
            stress_coefficient = 1.0
        else:
            denominator = max(taw_mm - raw, 1e-6)
            stress_coefficient = max(0.0, min(1.0, (taw_mm - depletion) / denominator))

        actual_et = stress_coefficient * crop_et
        actual_et_sum += actual_et
        if stress_coefficient < 0.999:
            stress_days += 1

        depletion = depletion - float(precip[day]) + actual_et

        if allow_irrigation and depletion > raw:
            applied = (depletion - raw) / irrigation_efficiency
            irrigation_mm += applied
            depletion -= applied * irrigation_efficiency

        depletion = float(np.clip(depletion, 0.0, taw_mm))

    if crop_et_sum > 0:
        ratio = actual_et_sum / crop_et_sum
        relative_yield = 1.0 - ky * (1.0 - ratio)
    else:
        relative_yield = 1.0

    return {
        "water_stress_days": float(stress_days),
        "irrigation_need_mm": round(irrigation_mm, 2),
        "relative_yield_index": round(max(0.0, min(1.0, relative_yield)), 4),
        "crop_et_sum_mm": round(crop_et_sum, 2),
        "actual_et_sum_mm": round(actual_et_sum, 2),
    }


def simulate_crop_season(
    crop: dict,
    soil: dict,
    tmax_c: np.ndarray,
    tmin_c: np.ndarray,
    precip_mm: np.ndarray,
    lat_deg: float,
    day_of_year: np.ndarray,
    irrigation_efficiency: float = 0.8,
    allow_irrigation: bool = True,
) -> dict[str, float]:
    et0 = et0_hargreaves(tmax_c, tmin_c, lat_deg, day_of_year)
    duration = int(crop["duration_days"])
    kc = kc_curve(
        duration,
        float(crop.get("kc_ini", 0.4)),
        float(crop["kc_mid"]),
        float(crop.get("kc_end", 0.6)),
    )
    days = min(duration, et0.size, np.asarray(precip_mm).size)
    taw = total_available_water_mm(soil, float(crop["rooting_depth_m"]))
    return simulate_season(
        np.asarray(precip_mm)[:days],
        et0[:days],
        kc[:days],
        taw,
        irrigation_efficiency=irrigation_efficiency,
        allow_irrigation=allow_irrigation,
    )
