import { tool } from "@openai/agents";
import { z } from "zod";
import { queryOne } from "@/lib/db";
import {
  getPowerClimatology,
  getPowerDaily,
  monthKeyFromDate,
  NASA_POWER_ATTRIBUTION,
} from "@/lib/weather/nasa-power";

type FarmRow = {
  id: string;
  name: string;
  location: string;
  district: string;
  lat: number;
  lng: number;
  primary_crop: string | null;
};

const MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"] as const;

function round1(n: number) {
  return Math.round(n * 10) / 10;
}

export function createGetNasaClimateTool(accountId: string) {
  return tool({
    name: "get_nasa_climate",
    description:
      "Get real NASA POWER agroclimatology data for a specific farm (by farmId). Returns long-term monthly climate normals (temperature, rainfall, humidity, soil wetness) and compares recent rainfall to normals to help answer if this is a drought/wet year for that farm. Use when the farmer asks about drought, rainfall trends, climate normals, or 'is this a drought year for my farm?'.",
    parameters: z.object({
      farmId: z.string().describe("The farm ID to fetch NASA POWER climate data for"),
    }),
    async execute({ farmId }) {
      const farm = await queryOne<FarmRow>(
        `SELECT id, name, location, district, lat, lng, primary_crop
         FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL`,
        [farmId, accountId],
      );
      if (!farm) {
        return "Farm not found or does not belong to you. Please check the farm ID.";
      }

      const lat = Number(farm.lat);
      const lng = Number(farm.lng);
      const [clim, recentDaily] = await Promise.all([
        getPowerClimatology(lat, lng),
        (async () => {
          const now = new Date();
          const endYear = now.getUTCFullYear();
          const start = `${endYear - 1}0101`;
          const end = `${endYear}${String(now.getUTCMonth() + 1).padStart(2, "0")}${String(now.getUTCDate()).padStart(2, "0")}`;
          return getPowerDaily(lat, lng, start, end, "PRECTOTCORR,T2M,GWETROOT,RH2M");
        })(),
      ]);

      if (!clim) {
        return `NASA POWER climate data is currently unavailable for ${farm.name} (${farm.location}, ${farm.district}). Try again later.`;
      }

      const lines: string[] = [];
      lines.push(`NASA POWER agroclimatology for ${farm.name} (${farm.location}, ${farm.district}, ${lat.toFixed(3)}, ${lng.toFixed(3)})`);
      lines.push(`Source: ${NASA_POWER_ATTRIBUTION} (AG community climatology normals and daily data)`);
      lines.push("");

      const currentMonth = monthKeyFromDate(new Date().toISOString().slice(0, 10));
      const cm = currentMonth;
      const tAvg = clim.T2M[cm];
      const tMax = clim.T2M_MAX[cm];
      const tMin = clim.T2M_MIN[cm];
      const rain = clim.PRECTOTCORR[cm];
      const rh = clim.RH2M[cm];
      const gwRoot = clim.GWETROOT[cm];
      const gwTop = clim.GWETTOP[cm];

      lines.push(`Current month normal (${cm}):`);
      if (tAvg != null && tAvg !== -999) lines.push(`- Avg temperature: ${round1(tAvg)}°C (max ${round1(tMax ?? tAvg)}°C, min ${round1(tMin ?? tAvg)}°C)`);
      if (rain != null && rain !== -999) lines.push(`- Rainfall: ${round1(rain)} mm/day (monthly normal)`);
      if (rh != null && rh !== -999) lines.push(`- Relative humidity: ${round1(rh)}%`);
      if (gwRoot != null && gwRoot !== -999) lines.push(`- Root-zone soil wetness (GWETROOT): ${round1(gwRoot)} (0=dry, 1=saturated)`);
      if (gwTop != null && gwTop !== -999) lines.push(`- Surface soil wetness (GWETTOP): ${round1(gwTop)} (0=dry, 1=saturated)`);
      lines.push("");

      // Annual normals summary
      const annualRain = clim.PRECTOTCORR["ANN"];
      const annualTemp = clim.T2M["ANN"];
      if ((annualRain != null && annualRain !== -999) || (annualTemp != null && annualTemp !== -999)) {
        lines.push("Annual normals:");
        if (annualTemp != null && annualTemp !== -999) lines.push(`- Avg temperature: ${round1(annualTemp)}°C`);
        if (annualRain != null && annualRain !== -999) lines.push(`- Avg precipitation: ${round1(annualRain)} mm/day (~${round1(annualRain * 365)} mm/year equivalent)`);
        lines.push("");
      }

      // Recent rainfall vs normal (simple drought/wet signal)
      if (recentDaily && recentDaily.length > 0) {
        const byMonth = new Map<string, { sum: number; count: number }>();
        let recentTotal = 0;
        let recentCount = 0;
        for (const d of recentDaily) {
          const p = d.PRECTOTCORR;
          if (p == null || p === -999) continue;
          recentTotal += p;
          recentCount++;
          const mk = monthKeyFromDate(d.date);
          const cur = byMonth.get(mk) ?? { sum: 0, count: 0 };
          cur.sum += p;
          cur.count += 1;
          byMonth.set(mk, cur);
        }
        if (recentCount > 0) {
          const now = new Date();
          const year = now.getUTCFullYear();
          let normalSum = 0;
          let actualSum = 0;
          let monthsCompared = 0;
          for (const [mk, v] of byMonth) {
            const normal = clim.PRECTOTCORR[mk];
            if (normal == null || normal === -999) continue;
            const actualAvg = v.sum / v.count;
            normalSum += normal;
            actualSum += actualAvg;
            monthsCompared++;
          }
          if (monthsCompared >= 2) {
            const ratio = normalSum > 0 ? actualSum / normalSum : 1;
            const pct = Math.round((ratio - 1) * 100);
            let signal = "near normal";
            if (ratio < 0.75) signal = "drier than normal (possible drought signal)";
            else if (ratio < 0.9) signal = "below normal rainfall";
            else if (ratio > 1.25) signal = "wetter than normal";
            else if (ratio > 1.1) signal = "above normal rainfall";
            lines.push(`Recent rainfall vs NASA POWER normals (last ~${monthsCompared} months with data):`);
            lines.push(`- Recent avg daily precip (observed period): ${round1(actualSum / monthsCompared)} mm/day`);
            lines.push(`- Normal avg daily precip (same months): ${round1(normalSum / monthsCompared)} mm/day`);
            lines.push(`- Difference: ${pct >= 0 ? "+" : ""}${pct}% (${signal})`);
            if (ratio < 0.75) {
              lines.push("- Interpretation: conditions indicate below-normal moisture; check soil wetness and plan irrigation/crop choices accordingly.");
            } else if (ratio > 1.25) {
              lines.push("- Interpretation: wetter-than-normal period; watch for waterlogging and disease pressure.");
            }
            lines.push("");
          }
        }
      }

      // Compact monthly rainfall normals for context
      const rainLine = MONTHS.map((m) => {
        const v = clim.PRECTOTCORR[m];
        return `${m}:${v != null && v !== -999 ? round1(v) : "n/a"}`;
      }).join(", ");
      lines.push(`Monthly rainfall normals (mm/day): ${rainLine}`);
      const wetLine = MONTHS.map((m) => {
        const v = clim.GWETROOT[m];
        return `${m}:${v != null && v !== -999 ? round1(v) : "n/a"}`;
      }).join(", ");
      lines.push(`Monthly root-zone soil wetness normals (0-1): ${wetLine}`);
      lines.push("");
      lines.push("Note: NASA POWER provides satellite/reanalysis-derived climatology and is best used as local climate context alongside on-ground observations.");

      return lines.join("\n");
    },
  });
}