import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache
def load_crops() -> dict[str, dict]:
    with (_DATA_DIR / "crops.json").open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache
def load_soils() -> dict[str, dict]:
    with (_DATA_DIR / "soils.json").open(encoding="utf-8") as handle:
        return json.load(handle)
