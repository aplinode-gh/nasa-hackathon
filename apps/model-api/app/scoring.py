from __future__ import annotations

from app.knowledge import load_crops, load_soils
from app.schemas import (
    CompareRotationsRequest,
    CompareRotationsResponse,
    OutcomeBand,
    Priorities,
    RotationStrategy,
    Scenario,
    Season,
    StrategyOutcome,
)

WATER_USE_MM = {"low": 350.0, "medium": 550.0, "high": 800.0}
WATER_SCORE = {"low": 1.0, "medium": 0.55, "high": 0.2}

GAPS = [
    "Outcome estimates are heuristic (crop and soil knowledge base only) until NASA features and the simulation-trained surrogate are wired in.",
    "Validate agronomic suitability with local extension services before changing rotations.",
]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _weights(priorities: Priorities) -> dict[str, float]:
    raw = {
        "water": priorities.water,
        "income": priorities.income,
        "soil_health": priorities.soil_health,
        "risk": priorities.risk,
    }
    total = sum(raw.values())
    if total <= 0:
        return {key: 0.25 for key in raw}
    return {key: value / total for key, value in raw.items()}


def _crop_dimensions(crop: dict) -> dict[str, float]:
    soil = _clamp(
        0.45 * ((crop["soc_effect"] + 1) / 2)
        + 0.35 * crop["erosion_cover"]
        + (0.2 if crop["n_fixing"] else 0.0)
    )
    risk = _clamp(1 - (0.5 * crop["market_volatility"] + 0.5 * crop["pest_pressure"]))
    return {
        "water": WATER_SCORE[crop["water_need"]],
        "income": _clamp(crop["market_score"]),
        "soil_health": soil,
        "risk": risk,
    }


def _crop_score(crop: dict, weights: dict[str, float]) -> float:
    dimensions = _crop_dimensions(crop)
    return sum(dimensions[key] * weights[key] for key in weights)


def _synergy(first: dict, second: dict) -> tuple[float, list[str]]:
    bonus = 0.05 * _clamp(second["soc_effect"], -1.0, 1.0)
    codes: list[str] = []
    if second["n_fixing"] and first["family"] == "cereal":
        bonus += 0.12
        codes.append("legume_after_cereal")
    if first["family"] != second["family"]:
        bonus += 0.08
        codes.append("family_diversity")
    if {first["water_need"], second["water_need"]} == {"low", "high"}:
        bonus += 0.05
        codes.append("water_complement")
    return bonus, codes


def _sequence_score(
    sequence: list[str], crops: dict[str, dict], weights: dict[str, float]
) -> tuple[float, list[str]]:
    base = sum(_crop_score(crops[crop_id], weights) for crop_id in sequence) / len(sequence)
    bonus = 0.0
    codes: list[str] = []
    for first_id, second_id in zip(sequence, sequence[1:]):
        added, found = _synergy(crops[first_id], crops[second_id])
        bonus += added
        codes.extend(found)
    return _clamp(base + bonus), codes


def _band(p50: float, spread_ratio: float = 0.15, hi: float | None = None) -> OutcomeBand:
    if hi is not None:
        p50 = _clamp(p50, 0.0, hi)
    spread = abs(p50) * spread_ratio
    p10 = p50 - spread
    p90 = p50 + spread
    if hi is not None:
        p10 = _clamp(p10, 0.0, hi)
        p90 = _clamp(p90, 0.0, hi)
    return OutcomeBand(p10=round(p10, 2), p50=round(p50, 2), p90=round(p90, 2))


def _outcomes(
    sequence: list[str],
    crops: dict[str, dict],
    soil: dict,
    weights: dict[str, float],
    scenario: Scenario,
) -> StrategyOutcome:
    sequence_crops = [crops[crop_id] for crop_id in sequence]
    water_use = sum(WATER_USE_MM[crop["water_need"]] for crop in sequence_crops) / len(
        sequence_crops
    )
    water_use = max(150.0, water_use * (1 - (scenario.precip_delta_pct / 100.0) * 0.5))

    availability = 0.6 + 0.4 * soil["water_holding_capacity"]
    irrigation = max(0.0, water_use * (1 - 0.35 * availability))

    mean_score = sum(_crop_score(crop, weights) for crop in sequence_crops) / len(sequence_crops)
    base_yield = sum(crop["baseline_yield_index"] for crop in sequence_crops) / len(sequence_crops)
    yield_index = base_yield * (0.7 + 0.3 * mean_score)

    soil_health = sum(_crop_dimensions(crop)["soil_health"] for crop in sequence_crops) / len(
        sequence_crops
    )
    erosion = sum(crop["erosion_cover"] for crop in sequence_crops) / len(sequence_crops)
    nitrogen = sum(1.0 for crop in sequence_crops if crop["n_fixing"]) / len(sequence_crops)
    market = sum(crop["market_score"] for crop in sequence_crops) / len(sequence_crops)
    families = len({crop["family"] for crop in sequence_crops})
    pest_break = _clamp(0.4 + 0.3 * (families - 1) + 0.3 * nitrogen)

    return StrategyOutcome(
        water_use_mm=_band(water_use),
        irrigation_need_mm=_band(irrigation),
        relative_yield_index=_band(yield_index, hi=1.0),
        soil_health=round(soil_health, 3),
        erosion_control=round(erosion, 3),
        nitrogen_fixation=round(nitrogen, 3),
        market_score=round(market, 3),
        pest_break=round(pest_break, 3),
    )


def _evidence(
    sequence: list[str],
    crops: dict[str, dict],
    codes: list[str],
    scenario: Scenario,
) -> list[str]:
    sequence_crops = [crops[crop_id] for crop_id in sequence]
    names = " → ".join(crop["name"] for crop in sequence_crops)
    evidence = [f"Sequence evaluated: {names}."]
    if "legume_after_cereal" in codes:
        evidence.append(
            "The legume fixes nitrogen, improving soil fertility for the following cereal."
        )
    if "family_diversity" in codes:
        evidence.append(
            "The crops come from different families, helping break pest and disease cycles."
        )
    if "water_complement" in codes:
        evidence.append(
            "The sequence mixes high- and low-water crops, spreading demand across the season."
        )
    for crop in sequence_crops:
        if crop["water_need"] == "low":
            evidence.append(f"{crop['name']} has low water demand, easing pressure under dry conditions.")
        if crop["soc_effect"] > 0.15:
            evidence.append(f"{crop['name']} adds organic matter, supporting long-term soil health.")
    if scenario.precip_delta_pct != 0:
        evidence.append(
            f"Scenario assumes a {scenario.precip_delta_pct:+.0f}% change in precipitation."
        )
    return evidence


def _risks(sequence: list[str], crops: dict[str, dict], soil: dict) -> list[str]:
    risks: list[str] = []
    for crop_id in sequence:
        crop = crops[crop_id]
        if crop["water_need"] == "high":
            risks.append(f"{crop['name']} has high water demand.")
        if crop["market_volatility"] >= 0.55:
            risks.append(f"{crop['name']} prices are volatile.")
        if crop["salinity_tolerance"] < 0.4 and soil["salinity"] > 0.5:
            risks.append(f"{crop['name']} is sensitive to saline soil.")
    return risks


def _default_candidates(crops: dict[str, dict], current: str, season: Season) -> list[str]:
    ids = [
        crop_id
        for crop_id, crop in crops.items()
        if crop_id != current and season.value in crop["season_windows"]
    ]
    ids.sort(key=lambda crop_id: crops[crop_id]["market_score"], reverse=True)
    return ids[:3]


def _label(sequence: list[str], crops: dict[str, dict], is_baseline: bool) -> str:
    names = " → ".join(crops[crop_id]["name"] for crop_id in sequence)
    return f"Existing rotation: {names}" if is_baseline else names


def build_response(request: CompareRotationsRequest) -> CompareRotationsResponse:
    crops = load_crops()
    soils = load_soils()
    weights = _weights(request.priorities)
    soil = soils[request.field.soil_type.value]
    current = request.field.current_crop

    candidates = request.candidate_crops or _default_candidates(
        crops, current, request.field.target_season
    )

    sequences: list[list[str]] = [[current, current]]
    for candidate in candidates:
        if candidate != current:
            sequences.append([current, candidate])

    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for sequence in sequences:
        key = tuple(sequence)
        if key not in seen:
            seen.add(key)
            unique.append(sequence)

    scored = [(sequence, *_sequence_score(sequence, crops, weights)) for sequence in unique]
    baseline = scored[0]
    alternatives = sorted(scored[1:], key=lambda item: item[1], reverse=True)[:3]

    strategies: list[RotationStrategy] = []
    for sequence, score, codes in [baseline, *alternatives]:
        is_baseline = sequence == [current, current]
        strategies.append(
            RotationStrategy(
                strategy_id=f"{'baseline' if is_baseline else 'alt'}-{'-'.join(sequence)}",
                label=_label(sequence, crops, is_baseline),
                sequence=sequence,
                is_baseline=is_baseline,
                score=round(score, 3),
                outcomes=_outcomes(sequence, crops, soil, weights, request.scenario),
                evidence=_evidence(sequence, crops, codes, request.scenario),
                gaps=list(GAPS),
                risks=_risks(sequence, crops, soil),
                confidence="low",
                data_sources=["crop_knowledge_base", "soil_knowledge_base"],
            )
        )

    return CompareRotationsResponse(
        field_id=request.field.field_id,
        strategies=strategies,
        priorities_used=request.priorities,
    )
