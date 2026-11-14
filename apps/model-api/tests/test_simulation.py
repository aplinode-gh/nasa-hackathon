import numpy as np

from app.simulation import (
    et0_hargreaves,
    kc_curve,
    simulate_season,
    total_available_water_mm,
)


def test_kc_curve_shape_and_bounds() -> None:
    curve = kc_curve(100, 0.4, 1.1, 0.5)
    assert curve.shape == (100,)
    assert curve.min() >= 0.4
    assert curve.max() <= 1.1


def test_et0_is_non_negative() -> None:
    doy = np.arange(1, 366)
    et0 = et0_hargreaves(np.full(365, 40.0), np.full(365, 20.0), 30.0, doy)
    assert et0.shape == (365,)
    assert np.all(et0 >= 0.0)


def test_total_available_water_positive() -> None:
    assert total_available_water_mm({"water_holding_capacity": 0.6}, 1.2) > 0.0


def test_rainfed_dry_season_reduces_yield() -> None:
    result = simulate_season(
        np.zeros(30), np.full(30, 8.0), np.full(30, 1.0), taw_mm=120.0, allow_irrigation=False
    )
    assert result["irrigation_need_mm"] == 0.0
    assert result["water_stress_days"] > 0
    assert result["relative_yield_index"] < 1.0


def test_irrigated_dry_season_receives_irrigation() -> None:
    result = simulate_season(
        np.zeros(30), np.full(30, 8.0), np.full(30, 1.0), taw_mm=120.0, allow_irrigation=True
    )
    assert result["irrigation_need_mm"] > 0.0


def test_wet_season_needs_no_irrigation() -> None:
    result = simulate_season(
        np.full(10, 50.0), np.full(10, 2.0), np.full(10, 1.0), taw_mm=150.0
    )
    assert result["irrigation_need_mm"] == 0.0
    assert result["relative_yield_index"] == 1.0
