"""Crop growth-stage helpers."""

from __future__ import annotations

from .constants import DEFAULT_STAGE, STAGE_SEQUENCES


def default_stages_for_crops(crops: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for crop in crops:
        key = (crop or "").lower()
        sequence = STAGE_SEQUENCES.get(key, STAGE_SEQUENCES["wheat"])
        out[key] = sequence[0]
    return out


def auto_advance_stage(stage_map: dict[str, str], record_type: str, crop: str) -> dict[str, str]:
    key = (crop or "").lower()
    current = stage_map.get(key)
    sequence = STAGE_SEQUENCES.get(key, STAGE_SEQUENCES["wheat"])
    try:
        current_index = sequence.index(current or DEFAULT_STAGE)
    except ValueError:
        current_index = 0

    new_map = dict(stage_map)
    if record_type in ("sowing", "planting"):
        if current and current != DEFAULT_STAGE:
            return new_map
        new_index = max(current_index, 1)
        if new_index != current_index:
            new_map[key] = sequence[new_index]
    elif record_type == "harvest":
        new_index = len(sequence) - 1
        if new_index != current_index:
            new_map[key] = sequence[new_index]
    return new_map
