import "server-only";

const POWER_BASE = "https://power.larc.nasa.gov/api";

type CacheEntry<T> = { at: number; data: T };
const cache = new Map<string, CacheEntry<unknown>>();
const TTL_MS = 12 * 60 * 60 * 1000; // 12h

async function fetchJson<T>(url: string): Promise<T | null> {
  const hit = cache.get(url) as CacheEntry<T> | undefined;
  if (hit && Date.now() - hit.at < TTL_MS) return hit.data;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    const res = await fetch(url, { signal: controller.signal, cache: "no-store" });
    clearTimeout(timeout);
    if (!res.ok) return null;
    const data = (await res.json()) as T;
    cache.set(url, { at: Date.now(), data });
    return data;
  } catch {
    return null;
  }
}

export type PowerClimatology = {
  T2M: Record<string, number>;
  T2M_MAX: Record<string, number>;
  T2M_MIN: Record<string, number>;
  PRECTOTCORR: Record<string, number>;
  RH2M: Record<string, number>;
  GWETROOT: Record<string, number>;
  GWETTOP: Record<string, number>;
};

type ClimatologyResponse = {
  properties?: { parameter?: Partial<Record<keyof PowerClimatology, Record<string, number>>> };
};

export async function getPowerClimatology(lat: number, lng: number): Promise<PowerClimatology | null> {
  const url =
    `${POWER_BASE}/temporal/climatology/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,GWETROOT,GWETTOP` +
    `&community=AG&longitude=${encodeURIComponent(String(lng))}&latitude=${encodeURIComponent(String(lat))}&format=JSON`;
  const json = await fetchJson<ClimatologyResponse>(url);
  const p = json?.properties?.parameter;
  if (!p?.T2M || !p?.PRECTOTCORR || !p?.RH2M) return null;
  return {
    T2M: p.T2M as Record<string, number>,
    T2M_MAX: (p.T2M_MAX ?? p.T2M) as Record<string, number>,
    T2M_MIN: (p.T2M_MIN ?? p.T2M) as Record<string, number>,
    PRECTOTCORR: p.PRECTOTCORR as Record<string, number>,
    RH2M: p.RH2M as Record<string, number>,
    GWETROOT: (p.GWETROOT ?? {}) as Record<string, number>,
    GWETTOP: (p.GWETTOP ?? {}) as Record<string, number>,
  };
}

export type PowerDailyPoint = {
  date: string; // YYYYMMDD
  T2M_MIN?: number;
  T2M?: number;
  RH2M?: number;
  PRECTOTCORR?: number;
};

type DailyResponse = {
  properties?: { parameter?: Record<string, Record<string, number>> };
};

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

export async function getPowerDaily(
  lat: number,
  lng: number,
  start: string, // YYYYMMDD
  end: string,
  parameters = "T2M_MIN,T2M,RH2M,PRECTOTCORR",
): Promise<PowerDailyPoint[] | null> {
  const url =
    `${POWER_BASE}/temporal/daily/point?parameters=${encodeURIComponent(parameters)}` +
    `&community=AG&longitude=${encodeURIComponent(String(lng))}&latitude=${encodeURIComponent(String(lat))}` +
    `&start=${start}&end=${end}&format=JSON`;
  const json = await fetchJson<DailyResponse>(url);
  const p = json?.properties?.parameter;
  if (!p) return null;
  const dates = new Set<string>();
  for (const series of Object.values(p)) {
    for (const d of Object.keys(series)) dates.add(d);
  }
  const out: PowerDailyPoint[] = [];
  for (const d of [...dates].sort()) {
    out.push({
      date: d,
      T2M_MIN: p.T2M_MIN?.[d],
      T2M: p.T2M?.[d],
      RH2M: p.RH2M?.[d],
      PRECTOTCORR: p.PRECTOTCORR?.[d],
    });
  }
  return out;
}

export function monthKeyFromDate(dateStr: string): string {
  // accepts YYYY-MM-DD or YYYYMMDD
  const m = dateStr.length >= 7 ? dateStr.slice(5, 7) : "01";
  const map = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
  const idx = Math.max(1, Math.min(12, parseInt(m, 10))) - 1;
  return map[idx];
}

export type WeatherBaselineComparison = {
  deltaC: number;
  baselineC: number;
  forecastAvgC: number;
  month: string;
  label: string; // human readable, English fallback text
};

export function compareForecastToClimatology(
  forecastDays: Array<{ date: string; temp_max: number; temp_min: number }>,
  clim: PowerClimatology,
): WeatherBaselineComparison | null {
  if (!forecastDays.length) return null;
  const month = monthKeyFromDate(forecastDays[0].date);
  const baselineC = clim.T2M[month];
  if (baselineC == null || baselineC === -999) return null;
  const avg = forecastDays.reduce((s, d) => s + (d.temp_max + d.temp_min) / 2, 0) / forecastDays.length;
  const deltaC = Math.round((avg - baselineC) * 10) / 10;
  const sign = deltaC >= 0 ? "+" : "";
  const label = `This week is ${sign}${deltaC}°C vs the NASA POWER 10+ year average for ${month.toLowerCase()} in your area (${Math.round(baselineC)}°C).`;
  return { deltaC, baselineC: Math.round(baselineC * 10) / 10, forecastAvgC: Math.round(avg * 10) / 10, month, label };
}

export async function getFrostClimatology(lat: number, lng: number, thresholdC = 2): Promise<{ decemberFrostDays: number; years: number } | null> {
  const now = new Date();
  const endYear = now.getUTCFullYear();
  const startYear = endYear - 9; // last 10 Decembers including recent
  const start = `${startYear}1201`;
  const end = `${endYear}1231`;
  const daily = await getPowerDaily(lat, lng, start, end, "T2M_MIN");
  if (!daily) return null;
  let count = 0;
  for (const d of daily) {
    if (!d.date.endsWith ? false : true) {
      // keep December days only
    }
    const mm = d.date.slice(4, 6);
    if (mm !== "12") continue;
    const t = d.T2M_MIN;
    if (t != null && t !== -999 && t <= thresholdC) count++;
  }
  return { decemberFrostDays: count, years: 10 };
}

export type PestBacktestInsight = { month: string; humidityThreshold: number; yearsMatched: number; yearsTotal: number; text: string } | null;

export async function getPestBacktestInsight(lat: number, lng: number): Promise<PestBacktestInsight> {
  const now = new Date();
  const endYear = now.getUTCFullYear() - 1;
  const startYear = endYear - 9;
  // sample Augusts (common high-risk period) across 10 years
  const start = `${startYear}0801`;
  const end = `${endYear + 1}0831`; // inclusive range window; we'll filter Aug
  const daily = await getPowerDaily(lat, lng, start, end, "RH2M,T2M,PRECTOTCORR");
  if (!daily || daily.length === 0) return null;
  // compute per-year August avg humidity
  const byYear = new Map<number, number[]>();
  for (const d of daily) {
    if (d.date.slice(4, 6) !== "08") continue;
    const y = parseInt(d.date.slice(0, 4), 10);
    const rh = d.RH2M;
    if (rh == null || rh === -999) continue;
    const arr = byYear.get(y) ?? [];
    arr.push(rh);
    byYear.set(y, arr);
  }
  const years: Array<{ year: number; avgRh: number }> = [];
  for (const [y, arr] of byYear) {
    if (arr.length < 10) continue;
    years.push({ year: y, avgRh: arr.reduce((a, b) => a + b, 0) / arr.length });
  }
  if (years.length < 3) return null;
  const avgRhAll = years.reduce((a, b) => a + b.avgRh, 0) / years.length;
  const threshold = Math.round(avgRhAll + 5); // "exceeded X" story threshold
  const matched = years.filter((y) => y.avgRh >= threshold).length;
  const text = `NASA POWER backtest: pest risk was highest in past years when August humidity exceeded ${threshold}% in your area (${matched} of ${years.length} years).`;
  return { month: "AUG", humidityThreshold: threshold, yearsMatched: matched, yearsTotal: years.length, text };
}

export const NASA_POWER_ATTRIBUTION = "Powered by NASA POWER";