import type {
  CropSummary,
  IrrigationType,
  RevenueConfidence,
  Season,
  SoilType,
  WaterLevel,
  CropCategory,
} from "./api-types";

/** Demo-tuned weights (research §2). Sum = 1.00. */
export const WEIGHTS = {
  suitability: 0.3,
  weather: 0.2,
  profit: 0.25,
  risk: 0.15,
  sustain: 0.1,
} as const;

const clamp01 = (n: number): number => Math.max(0, Math.min(1, n));

export type PriceInfo = {
  /** PKR per maan (≈40 kg) for the most recent observation. */
  pricePerMaanPkr: number;
  trend: "up" | "stable" | "down";
  volatility: number;
};

export type ScoreContext = {
  soilType: SoilType;
  season: Season;
  budget: "low" | "medium" | "high" | "very_high";
  irrigation: IrrigationType;
  /** true when a live weather forecast was available for the farm. */
  weatherAvailable: boolean;
  /** true when per-crop price trends were available. */
  marketAvailable: boolean;
  soilConfidence: "full" | "degraded" | "missing";
  /** suitability score (0..1) per crop id from crop_soil_compatibility. */
  compatibilityByCrop: Record<string, number>;
  /** latest price info per crop id. */
  priceByCrop: Record<string, PriceInfo>;
  /** category of the farm's most recent past crop (for rotation fit). */
  lastCropCategory?: CropCategory | null;
  /** NASA POWER climatology inputs (real rainfall/soil wetness) when available. */
  nasa?: {
    rainfallMmMonth: number | null; // PRECTOTCORR mm/day-ish monthly mean
    soilWetnessRoot: number | null; // GWETROOT 0-1
    soilWetnessTop: number | null; // GWETTOP 0-1
  };
};

const RISK_BASE: Record<"low" | "medium" | "high", number> = {
  low: 0.2,
  medium: 0.5,
  high: 0.8,
};

const WATER_SCORE: Record<WaterLevel, number> = { low: 1, medium: 0.7, high: 0.4 };

/** 1 maan ≈ 40 kg. */
const MAAN_KG = 40;

export function revenuePerAcre(
  crop: CropSummary,
  pricePerMaanPkr: number,
): number {
  const pricePerKg = pricePerMaanPkr / MAAN_KG;
  return Math.round(crop.typicalYieldPerAcreKg * pricePerKg);
}

function suitabilityScore(crop: CropSummary, ctx: ScoreContext): number {
  const base = ctx.compatibilityByCrop[crop.id] ?? 0.6;
  let s = base;
  if (crop.waterRequirementLevel === "high" && ctx.irrigation === "rainfed") {
    s -= 0.25;
  }
  if (crop.waterRequirementLevel === "low" && ctx.irrigation === "canal") {
    s += 0.02;
  }
  return clamp01(s);
}

function weatherFitScore(crop: CropSummary, ctx: ScoreContext): number {
  if (!ctx.weatherAvailable && !ctx.nasa?.rainfallMmMonth) return 0.65;

  // Season dimension (25): use NASA POWER rainfall climatology when available to judge season fit.
  const rain = ctx.nasa?.rainfallMmMonth;
  const need = crop.waterRequirementLevel;
  let seasonScore = 0.72;
  if (rain != null && rain >= 0 && rain < 900) {
    // Compare monthly rainfall (mm/day) to crop water need.
    const ideal = need === "high" ? 5 : need === "medium" ? 2.5 : 1.2;
    const diff = Math.abs(rain - ideal);
    seasonScore = clamp01(1 - diff / 8);
  } else {
    const seasonFit: Record<Season, number> = {
      summer: crop.category === "vegetable" ? 0.8 : 0.72,
      winter: crop.category === "staple" ? 0.82 : 0.7,
      autumn: 0.74,
      spring: 0.76,
      rainy: need === "high" ? 0.85 : 0.68,
      windy: 0.7,
    };
    seasonScore = seasonFit[ctx.season];
  }

  // Irrigation/wetness dimension (15): use NASA POWER root-zone soil wetness (GWETROOT).
  const gwet = ctx.nasa?.soilWetnessRoot ?? ctx.nasa?.soilWetnessTop;
  let irrigationScore = 0.7;
  if (gwet != null && gwet >= 0 && gwet <= 1) {
    const wetNeed = need === "high" ? 0.55 : need === "medium" ? 0.4 : 0.28;
    if (ctx.irrigation === "rainfed") {
      irrigationScore = clamp01(1 - Math.abs(gwet - wetNeed));
    } else if (ctx.irrigation === "canal" || ctx.irrigation === "tubewell" || ctx.irrigation === "mixed") {
      // irrigation buffers dryness; penalize only extreme mismatch
      irrigationScore = clamp01(0.75 + (gwet >= wetNeed * 0.6 ? 0.2 : -0.15));
    }
  } else {
    if (need === "high" && ctx.irrigation === "rainfed") irrigationScore = 0.45;
    else if (need === "low" && ctx.irrigation === "canal") irrigationScore = 0.82;
  }

  // Blend with Season ~25 and Irrigation ~15 parts (of a 40-like subscale) => 25/40,15/40
  return clamp01(seasonScore * 0.625 + irrigationScore * 0.375);
}

function profitabilityScore(crop: CropSummary, ctx: ScoreContext): number {
  if (!ctx.marketAvailable) return 0.6;
  const price = ctx.priceByCrop[crop.id];
  if (!price) return 0.55;
  const revenue = revenuePerAcre(crop, price.pricePerMaanPkr);
  const marginShare = (revenue - crop.capitalRequirementPerAcrePkr) / (revenue + 1);
  let p = clamp01(0.5 + marginShare);
  if (price.trend === "up") p += 0.1;
  else if (price.trend === "down") p -= 0.1;
  return clamp01(p);
}

function riskScore(crop: CropSummary, ctx: ScoreContext): number {
  const base = RISK_BASE[crop.marketRiskBaseline];
  const vol = ctx.priceByCrop[crop.id]?.volatility ?? 0.15;
  return clamp01(base + vol * 0.3);
}

function sustainabilityScore(crop: CropSummary, ctx: ScoreContext): number {
  const nitrogen = crop.category === "pulse" ? 1 : 0.5;
  const water = WATER_SCORE[crop.waterRequirementLevel];
  const rotationFit =
    ctx.lastCropCategory && ctx.lastCropCategory !== crop.category ? 0.9 : 0.6;
  return clamp01(0.5 * nitrogen + 0.3 * water + 0.2 * rotationFit);
}

export type ScoredCrop = {
  crop: CropSummary;
  scores: {
    suitability: number;
    weatherFit: number;
    profitability: number;
    risk: number;
    sustainability: number;
    final: number;
  };
  expectedRevenuePerAcrePkr: number;
  revenueConfidence: RevenueConfidence;
  riskFactors: string[];
  dataSourcesUsed: string[];
};

export function scoreCrop(crop: CropSummary, ctx: ScoreContext): ScoredCrop {
  const suitability = suitabilityScore(crop, ctx);
  const weatherFit = weatherFitScore(crop, ctx);
  const profitability = profitabilityScore(crop, ctx);
  const risk = riskScore(crop, ctx);
  const sustainability = sustainabilityScore(crop, ctx);

  const hasWeatherSignals = ctx.weatherAvailable || Boolean(ctx.nasa?.rainfallMmMonth != null || ctx.nasa?.soilWetnessRoot != null);

  let wSum = 0;
  let acc = 0;
  wSum += WEIGHTS.suitability;
  acc += WEIGHTS.suitability * suitability;
  if (hasWeatherSignals) {
    wSum += WEIGHTS.weather;
    acc += WEIGHTS.weather * weatherFit;
  }
  if (ctx.marketAvailable) {
    wSum += WEIGHTS.profit;
    acc += WEIGHTS.profit * profitability;
  }
  wSum += WEIGHTS.risk;
  acc += WEIGHTS.risk * (1 - risk);
  wSum += WEIGHTS.sustain;
  acc += WEIGHTS.sustain * sustainability;

  const final = clamp01(wSum > 0 ? acc / wSum : 0);

  const price = ctx.priceByCrop[crop.id];
  const expectedRevenuePerAcrePkr =
    ctx.marketAvailable && price ? revenuePerAcre(crop, price.pricePerMaanPkr) : 0;

  const riskFactors: string[] = [];
  if (crop.marketRiskBaseline === "high" || (price && price.volatility > 0.3))
    riskFactors.push("price_volatility");
  if (crop.category === "vegetable") riskFactors.push("pest_pressure");
  if (crop.waterRequirementLevel === "high" && ctx.irrigation === "rainfed")
    riskFactors.push("water_stress");
  if (!hasWeatherSignals) riskFactors.push("weather");
  if (crop.capitalRequirementPerAcrePkr > 60000) riskFactors.push("input_cost");

  const revenueConfidence: RevenueConfidence = !ctx.marketAvailable
    ? "unreliable"
    : price && price.volatility > 0.4
      ? "low"
      : price && price.volatility > 0.15
        ? "medium"
        : "high";

  const dataSourcesUsed: string[] = [];
  if (ctx.weatherAvailable) dataSourcesUsed.push("weather");
  if (ctx.nasa?.rainfallMmMonth != null || ctx.nasa?.soilWetnessRoot != null) dataSourcesUsed.push("nasa_power");
  if (ctx.marketAvailable) dataSourcesUsed.push("market");
  dataSourcesUsed.push("soil");

  return {
    crop,
    scores: { suitability, weatherFit, profitability, risk, sustainability, final },
    expectedRevenuePerAcrePkr,
    revenueConfidence,
    riskFactors,
    dataSourcesUsed,
  };
}

/** Scores all candidates, sorts by final score, returns the top `limit`. */
export function rankCandidates(
  crops: CropSummary[],
  ctx: ScoreContext,
  limit = 3,
): ScoredCrop[] {
  return crops
    .map((crop) => scoreCrop(crop, ctx))
    .sort((a, b) => b.scores.final - a.scores.final)
    .slice(0, limit);
}
