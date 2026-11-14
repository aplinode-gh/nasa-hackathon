from app.datasets.build import SEASON_START, SITES
from app.knowledge import load_crops, load_soils


def test_all_sites_map_to_known_soil_and_province() -> None:
    soils = load_soils()
    for key, site in SITES.items():
        assert site["soil"] in soils, f"{key} has unknown soil {site['soil']}"
        assert site["province"], f"{key} is missing a province"
        assert -90.0 <= site["lat"] <= 90.0
        assert -180.0 <= site["lon"] <= 180.0


def test_all_crop_seasons_are_known() -> None:
    crops = load_crops()
    for name, crop in crops.items():
        assert crop["season_windows"], f"{name} has no season windows"
        for season in crop["season_windows"]:
            assert season in SEASON_START, f"{name} uses unknown season {season}"


def test_pakistan_has_multiple_provinces() -> None:
    provinces = {site["province"] for site in SITES.values()}
    assert len(provinces) >= 5
    assert "Sindh" in provinces
    assert "Punjab" in provinces
