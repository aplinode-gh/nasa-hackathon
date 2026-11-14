/**
 * Static UI build: alert scanning rules are kept (pure, forecast-driven).
 * Persistence and email delivery are not available, so runAlertScan is removed.
 */

import type { ForecastResult, ForecastHour } from "./openweather";

export type AlertType = "heavy_rain" | "frost" | "extreme_heat" | "disease_risk";
export type AlertSeverity = "warning" | "critical";

export type AlertCondition = {
  type: AlertType;
  severity: AlertSeverity;
  recommendationKey: string;
  conditionMet: Record<string, number>;
};

export type WeatherAlertRow = {
  id: string;
  farm_id: string;
  account_id: string;
  alert_type: AlertType;
  condition_met: Record<string, number>;
  recommendation: string;
  recommendation_key: string;
  severity: AlertSeverity;
  sent_via: string[];
  sent_at: string | null;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string;
};

const RECOMMENDATION_KEYS: Record<AlertType, string> = {
  heavy_rain: "app.weather.alerts.heavyRain",
  frost: "app.weather.alerts.frost",
  extreme_heat: "app.weather.alerts.extremeHeat",
  disease_risk: "app.weather.alerts.diseaseRisk",
};

/** Scan the next ~24 hours (8 × 3-hour steps) for imminent threats. */
export function scanAlertConditions(forecast: ForecastResult): AlertCondition[] {
  const seen = new Set<AlertType>();
  const found: AlertCondition[] = [];

  for (const step of forecast.hourly.slice(0, 8)) {
    if (step.precip_mm >= 10 && !seen.has("heavy_rain")) {
      seen.add("heavy_rain");
      found.push({
        type: "heavy_rain",
        severity: step.precip_mm >= 20 ? "critical" : "warning",
        recommendationKey: RECOMMENDATION_KEYS.heavy_rain,
        conditionMet: { precip_mm: step.precip_mm, temp_c: step.temp_c },
      });
    }
    if (step.temp_c < 2 && !seen.has("frost")) {
      seen.add("frost");
      found.push({
        type: "frost",
        severity: "warning",
        recommendationKey: RECOMMENDATION_KEYS.frost,
        conditionMet: { temp_c: step.temp_c },
      });
    }
    if (step.temp_c > 40 && !seen.has("extreme_heat")) {
      seen.add("extreme_heat");
      found.push({
        type: "extreme_heat",
        severity: "critical",
        recommendationKey: RECOMMENDATION_KEYS.extreme_heat,
        conditionMet: { temp_c: step.temp_c },
      });
    }
    if (
      step.humidity >= 80 &&
      step.temp_c >= 20 &&
      step.temp_c <= 30 &&
      !seen.has("disease_risk")
    ) {
      seen.add("disease_risk");
      found.push({
        type: "disease_risk",
        severity: "warning",
        recommendationKey: RECOMMENDATION_KEYS.disease_risk,
        conditionMet: { humidity: step.humidity, temp_c: step.temp_c },
      });
    }
  }
  return found;
}

/** Scan each day of the forecast for conditions that warrant an alert. */
export function scanDailyAlertConditions(
  forecast: ForecastResult,
): Record<string, AlertCondition[]> {
  const byDay: Record<string, AlertCondition[]> = {};
  const hourlyByDay: Record<string, ForecastHour[]> = {};

  for (const h of forecast.hourly) {
    const date = h.time.slice(0, 10);
    if (!hourlyByDay[date]) hourlyByDay[date] = [];
    hourlyByDay[date].push(h);
  }

  for (const [date, hours] of Object.entries(hourlyByDay)) {
    const seen = new Set<AlertType>();
    const alerts: AlertCondition[] = [];

    for (const step of hours) {
      if (step.precip_mm >= 5 && !seen.has("heavy_rain")) {
        seen.add("heavy_rain");
        alerts.push({
          type: "heavy_rain",
          severity: step.precip_mm >= 15 ? "critical" : "warning",
          recommendationKey: RECOMMENDATION_KEYS.heavy_rain,
          conditionMet: { precip_mm: step.precip_mm, temp_c: step.temp_c },
        });
      }
      if (step.temp_c < 5 && !seen.has("frost")) {
        seen.add("frost");
        alerts.push({
          type: "frost",
          severity: "warning",
          recommendationKey: RECOMMENDATION_KEYS.frost,
          conditionMet: { temp_c: step.temp_c },
        });
      }
      if (step.temp_c > 38 && !seen.has("extreme_heat")) {
        seen.add("extreme_heat");
        alerts.push({
          type: "extreme_heat",
          severity: "critical",
          recommendationKey: RECOMMENDATION_KEYS.extreme_heat,
          conditionMet: { temp_c: step.temp_c },
        });
      }
      if (
        step.humidity >= 80 &&
        step.temp_c >= 20 &&
        step.temp_c <= 30 &&
        !seen.has("disease_risk")
      ) {
        seen.add("disease_risk");
        alerts.push({
          type: "disease_risk",
          severity: "warning",
          recommendationKey: RECOMMENDATION_KEYS.disease_risk,
          conditionMet: { humidity: step.humidity, temp_c: step.temp_c },
        });
      }
    }

    if (alerts.length > 0) {
      byDay[date] = alerts;
    }
  }

  return byDay;
}
