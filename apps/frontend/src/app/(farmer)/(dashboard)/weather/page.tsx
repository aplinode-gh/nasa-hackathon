import type { Metadata } from "next";
import Link from "next/link";
import PageHeader from "@/components/shell/page-header";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import { getWeatherBundle, getAppLocale, getDictionary } from "@/lib/i18n/server";
import type { CatalogKey } from "@/catalog";
import { type GrowthStage, type Severity } from "@/lib/weather/advisory";
import FarmSelector from "@/components/weather/FarmSelector";
import AdvisoryCard from "@/components/weather/AdvisoryCard";
import DailyAlertList from "@/components/weather/DailyAlertList";
import AlertBanner, { type AlertItem } from "@/components/weather/AlertBanner";
import RegisterFarmForm from "@/components/weather/RegisterFarmForm";
import WeatherDashboard from "@/components/weather/WeatherDashboard";
import { CROPS } from "@/lib/farms/constants";
import { scanAlertConditions, scanDailyAlertConditions, type AlertCondition } from "@/lib/weather/alerts";

export const metadata: Metadata = { title: "Weather — AgroAI" };

type FarmRow = {
  id: string;
  name: string;
  primary_crop: string | null;
  sowing_date: string | null;
  crops: string[] | string | null;
  lat: number | null;
  lng: number | null;
  location: string | null;
  district: string | null;
  growth_stages?: Record<string, string> | null;
};

type RecordRow = {
  type: string;
  event_date: string;
};

type ForecastHour = {
  time: string;
  temp_c: number;
  rain_pct: number;
  precip_mm: number;
  humidity: number;
  wind_kph: number;
  condition: string;
};

function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

function asCrops(value: FarmRow["crops"]): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  }
  return [];
}

export default async function WeatherPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  await requireSessionPage();
  const bundle = await getWeatherBundle();
  const locale = await getAppLocale();
  const dict = await getDictionary(locale);
  const t = dict.t;

  const farmsData = await backendFetch<any>("/api/farms");
  const farmList = (Array.isArray(farmsData) ? farmsData : farmsData?.farms ?? []) as FarmRow[];

  if (farmList.length === 0) {
    return (
      <div className="pt-1">
        <PageHeader eyebrow={bundle.eyebrow} title={bundle.pageTitle} description={bundle.description} />
        <section className="mt-5 rounded-3xl border border-agro-sprout bg-white p-6 text-center">
          <h2 className="text-lg font-semibold text-agro-forest">{bundle.registerTitle}</h2>
          <p className="mt-1 text-sm text-agro-slate">{bundle.registerBody}</p>
          <Link
            href="/farms/new"
            className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-agro-canopy px-5 text-sm font-semibold text-white transition-colors hover:bg-agro-forest"
          >
            {bundle.registerCta}
          </Link>
        </section>
      </div>
    );
  }

  const params = await searchParams;
  const requested = typeof params.farm === "string" ? params.farm : null;
  const selected =
    farmList.find((f) => String(f.id) === requested) ??
    farmList.find((f) => !!f.primary_crop) ??
    farmList[0];

  const stageLabels: Record<GrowthStage, string> = {
    seedling: bundle.stages.seedling,
    vegetative: bundle.stages.vegetative,
    flowering: bundle.stages.flowering,
    maturation: bundle.stages.maturation,
    harvestReady: bundle.stages.harvestReady,
    generic: bundle.stages.generic,
  };
  const severityLabels: Record<Severity, string> = {
    info: bundle.severity.info,
    warning: bundle.severity.warning,
    critical: bundle.severity.critical,
  };

  const farmOptions = farmList.map((f) => {
    const crops = asCrops(f.crops);
    return {
      id: String(f.id),
      name: String(f.name ?? ""),
      cropLabel: capitalize(String(f.primary_crop ?? crops[0] ?? "")),
      location: String(f.location ?? ""),
      district: String(f.district ?? ""),
    };
  });

  const latNum = selected.lat == null ? NaN : Number(selected.lat);
  const lngNum = selected.lng == null ? NaN : Number(selected.lng);
  if (!Number.isFinite(latNum) || !Number.isFinite(lngNum)) {
    return (
      <div className="pt-1">
        <PageHeader eyebrow={bundle.eyebrow} title={bundle.pageTitle} description={bundle.description} />
        <div className="mt-5">
          <FarmSelector farms={farmOptions} selectedId={String(selected.id)} label={bundle.farmSelectorLabel} />
        </div>
        <p className="mt-4 rounded-2xl border border-agro-canopy/30 bg-agro-mint px-4 py-3 text-sm text-agro-forest">
          {bundle.weatherUnavailable} — Please add location coordinates to your farm to see weather data.
        </p>
      </div>
    );
  }

  const [recordsData, forecastData, currentWeatherData, alertsData] = await Promise.all([
    backendFetch<any>(`/api/farms/${encodeURIComponent(String(selected.id))}/records?limit=20`),
    backendFetch<any>(`/api/weather/forecast?farm_id=${encodeURIComponent(String(selected.id))}`),
    backendFetch<any>(`/api/weather/current?lat=${encodeURIComponent(String(latNum))}&lng=${encodeURIComponent(String(lngNum))}`),
    backendFetch<any>("/api/weather/alerts"),
  ]);

  const recordList = (Array.isArray(recordsData) ? recordsData : recordsData?.records ?? []) as RecordRow[];
  const forecastUnavailable = !forecastData || !!forecastData.weather_data_unavailable;
  const rawDays = Array.isArray(forecastData?.raw_days) ? forecastData.raw_days : [];
  const hourly = Array.isArray(forecastData?.hourly) ? (forecastData.hourly as ForecastHour[]) : [];
  const advisoryDays = Array.isArray(forecastData?.advisory_days)
    ? forecastData.advisory_days
    : Array.isArray(forecastData?.days)
      ? forecastData.days
      : [];

  const effectiveCrop = forecastData?.effective_crop ?? null;
  if (!forecastUnavailable && !effectiveCrop && rawDays.length > 0) {
    return (
      <div className="pt-1">
        <PageHeader eyebrow={bundle.eyebrow} title={bundle.pageTitle} description={bundle.description} />
        <div className="mt-5">
          <FarmSelector farms={farmOptions} selectedId={String(selected.id)} label={bundle.farmSelectorLabel} />
        </div>
        <RegisterFarmForm
          farmId={String(selected.id)}
          cropOptions={[...(CROPS as readonly string[])]}
          strings={bundle.registerForm}
        />
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  const currentWeather = {
    condition: currentWeatherData?.condition ?? null,
    temp_c: currentWeatherData?.temp_c ?? null,
    humidity: currentWeatherData?.humidity ?? null,
    wind_kph: currentWeatherData?.wind_kph ?? null,
    fetched_at: currentWeatherData?.fetched_at ?? null,
  };

  const forecastForScan = !forecastUnavailable && rawDays.length > 0
    ? ({ days: rawDays, hourly, source: (forecastData?.source ?? "live") as "live" | "unavailable" } as any)
    : null;
  const staticAlertConditions: AlertCondition[] = forecastForScan ? scanAlertConditions(forecastForScan) : [];
  const rawDailyAlerts = forecastForScan ? scanDailyAlertConditions(forecastForScan) : {};
  const dailyAlerts: Record<string, Array<{ type: string; severity: Severity; recommendation: string }>> = {};
  for (const [date, alerts] of Object.entries(rawDailyAlerts)) {
    dailyAlerts[date] = alerts.map((a) => ({
      type: a.type,
      severity: a.severity,
      recommendation: t(a.recommendationKey as CatalogKey).text,
    }));
  }

  const todayAdviceRaw = advisoryDays.find((d: any) => d.date === today) ?? advisoryDays[0] ?? forecastData?.today ?? null;
  const todayAdvice = todayAdviceRaw
    ? {
        growth_stage: ((todayAdviceRaw.growth_stage as GrowthStage) ?? "generic") as GrowthStage,
        advice_text: String(todayAdviceRaw.advice_text ?? "Keep monitoring your crop and the forecast."),
        severity: ((todayAdviceRaw.severity as Severity) ?? "info") as Severity,
      }
    : null;

  const dbAlertsList = (alertsData?.alerts ?? []) as Array<any>;
  const staticAlerts: AlertItem[] = staticAlertConditions.map((c, i) => ({
    id: `static-${c.type}-${i}`,
    farmName: String(selected.name ?? ""),
    severity: c.severity,
    recommendation: t(c.recommendationKey as CatalogKey).text,
    alertType: c.type,
  }));
  const combinedAlerts: AlertItem[] = [
    ...staticAlerts,
    ...dbAlertsList.map((a) => ({
      id: String(a.id),
      farmName: String(a.farm_name ?? selected.name ?? ""),
      severity: ((a.severity as Severity) ?? "info") as Severity,
      recommendation: String(a.recommendation ?? ""),
      alertType: String(a.alert_type ?? ""),
    })),
  ];

  let dataSourceLabel = bundle.source.demo;
  if (forecastUnavailable) {
    if (forecastData?.source === "cached" || forecastData?.today) dataSourceLabel = bundle.source.cached;
  } else if (rawDays.length > 0) {
    dataSourceLabel = bundle.source.live;
  }

  const hourlyByDay: Record<string, ForecastHour[]> = {};
  for (const h of hourly) {
    const date = String(h.time ?? "").slice(0, 10);
    if (!date) continue;
    if (!hourlyByDay[date]) hourlyByDay[date] = [];
    hourlyByDay[date].push(h);
  }

  const recentRecords = recordList.slice(0, 5);
  const recordTypeLabels: Record<string, string> = {
    sowing: "Sowing",
    planting: "Planting",
    irrigation: "Irrigation",
    fertilizer: "Fertilizer",
    pesticide: "Pesticide",
    disease: "Disease",
    harvest: "Harvest",
  };

  const dateTime = new Date().toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  return (
    <div className="pt-1">
      <PageHeader eyebrow={bundle.eyebrow} title={bundle.pageTitle} description={bundle.description} />

      <div className="mt-5">
        <FarmSelector farms={farmOptions} selectedId={String(selected.id)} label={bundle.farmSelectorLabel} />
      </div>

      {forecastUnavailable && !forecastData?.today && rawDays.length === 0 && (
        <p className="mt-4 rounded-2xl border border-agro-canopy/30 bg-agro-mint px-4 py-3 text-sm text-agro-forest">
          <strong className="font-semibold">{bundle.weatherUnavailable}</strong> — {bundle.weatherUnavailableBody}
        </p>
      )}

      <WeatherDashboard
        currentWeather={currentWeather}
        farmName={String(selected.name ?? "")}
        farmLocation={String(selected.location ?? "")}
        farmDistrict={String(selected.district ?? "")}
        dateTime={dateTime}
        hourlyByDay={hourlyByDay as any}
        days={rawDays as any}
        selectedDay={today}
        metricLabels={{
          temperature: t("app.weather.metric.temperature").text,
          precipitation: t("app.weather.metric.precipitation").text,
          wind: t("app.weather.metric.wind").text,
        }}
        overviewLabels={{
          precipitation: t("app.weather.metric.precipitation").text,
          humidity: t("app.weather.metric.humidity").text,
          wind: t("app.weather.metric.wind").text,
        }}
      />

      {todayAdvice && (
        <AdvisoryCard
          severity={todayAdvice.severity}
          severityLabel={severityLabels[todayAdvice.severity]}
          growthStageLabel={stageLabels[todayAdvice.growth_stage] ?? stageLabels.generic}
          adviceText={todayAdvice.advice_text}
          dateLabel={bundle.todayAdvisory}
        />
      )}

      <AlertBanner
        alerts={combinedAlerts}
        title={bundle.alerts.title}
        dismissLabel={bundle.alerts.dismiss}
        noAlertsLabel={bundle.alerts.noAlerts}
        viewAllLabel={bundle.alerts.viewAll}
        viewAllHref="/notifications"
      />

      <p className="mt-4 flex items-center gap-2 font-mono text-[0.7rem] uppercase tracking-[0.18em] text-agro-slate">
        <span className="inline-flex h-2 w-2 rounded-full bg-agro-canopy" aria-hidden="true" />
        {dataSourceLabel}
      </p>

      {recentRecords.length > 0 && (
        <section className="mt-6" aria-labelledby="recent-records-heading">
          <h2 id="recent-records-heading" className="font-mono text-xs font-semibold uppercase tracking-[0.22em] text-agro-slate">
            Recent Activity
          </h2>
          <ul className="mt-3 divide-y divide-agro-sprout overflow-hidden rounded-2xl border border-agro-sprout bg-white">
            {recentRecords.map((record, idx) => (
              <li key={`${record.event_date}-${record.type}-${idx}`} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="font-medium text-agro-forest">{recordTypeLabels[record.type] || record.type}</span>
                <span className="text-agro-slate">{record.event_date}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {rawDays.length > 0 && (
        <DailyAlertList
          days={rawDays as any}
          dailyAlerts={dailyAlerts}
          title={bundle.forecastTitle}
          subtitle={bundle.forecastSubtitle}
          genericRecommendation={t("app.weather.advisory.recommendation.generic").text}
        />
      )}
    </div>
  );
}
