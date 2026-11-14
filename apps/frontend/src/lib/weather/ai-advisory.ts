/**
 * Static UI build: AI weather advice is not generated.
 *
 * The type surface is preserved so the weather screen type-checks; the batch
 * generator simply returns no advice, letting the UI fall back to its generic
 * advisory copy.
 */

export interface AIDayAdvice {
  advice_text: string;
  severity: "info" | "warning" | "critical";
  label: string;
}

export interface DayWeatherInput {
  date: string;
  temp_max: number;
  temp_min: number;
  precip_mm: number;
  humidity: number;
  description: string;
}

export async function generateAIAdviceBatch(_params: {
  days: DayWeatherInput[];
  crop: string;
  growthStage: string;
  locale: string;
  farmName: string;
  recentActivities: string[];
}): Promise<Map<string, AIDayAdvice>> {
  return new Map<string, AIDayAdvice>();
}
