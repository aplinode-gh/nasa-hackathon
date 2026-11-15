"use client";

import { useState } from "react";
import type { ForecastHour, ForecastDay } from "@/lib/weather/openweather";
import type { WeatherSnapshot } from "@/lib/farms/weather";
import WeatherOverview from "./WeatherOverview";
import WeatherMetricTabs from "./WeatherMetricTabs";
import HourlyWeatherChart from "./HourlyWeatherChart";
import WeeklyForecast from "./WeeklyForecast";

type Metric = "temperature" | "precipitation" | "wind";

type WeatherDashboardProps = {
  currentWeather: WeatherSnapshot | null;
  farmName: string;
  farmLocation: string;
  farmDistrict: string;
  dateTime: string;
  hourlyByDay: Record<string, ForecastHour[]>;
  days: ForecastDay[];
  selectedDay: string;
  metricLabels: {
    temperature: string;
    precipitation: string;
    wind: string;
  };
  overviewLabels: {
    precipitation: string;
    humidity: string;
    wind: string;
  };
  nasaBaseline?: string | null;
  nasaAttribution?: string | null;
  frostSummary?: string | null;
};

export default function WeatherDashboard({
  currentWeather,
  farmName,
  farmLocation,
  farmDistrict,
  dateTime,
  hourlyByDay,
  days,
  selectedDay,
  metricLabels,
  overviewLabels,
  nasaBaseline,
  nasaAttribution,
  frostSummary,
}: WeatherDashboardProps) {
  const [metric, setMetric] = useState<Metric>("temperature");
  const [activeDay, setActiveDay] = useState(selectedDay);

  const hours = hourlyByDay[activeDay] ?? [];

  return (
    <div className="mt-6 space-y-6">
      <WeatherOverview
        temp={currentWeather?.temp_c ?? null}
        condition={currentWeather?.condition ?? null}
        humidity={currentWeather?.humidity ?? null}
        precipitation={hours[0]?.rain_pct ?? null}
        wind={currentWeather?.wind_kph ?? null}
        farmName={farmName}
        farmLocation={farmLocation}
        farmDistrict={farmDistrict}
        dateTime={dateTime}
        labels={overviewLabels}
      />

      {(nasaBaseline || frostSummary || nasaAttribution) && (
        <section className="rounded-2xl border border-agro-sprout bg-agro-mint/30 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-agro-forest">NASA climate context</h3>
            {nasaAttribution && (
              <span className="inline-flex items-center rounded-full border border-agro-canopy/30 bg-white px-2.5 py-1 font-mono text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-agro-canopy">
                {nasaAttribution}
              </span>
            )}
          </div>
          {nasaBaseline && <p className="mt-2 text-sm leading-relaxed text-agro-ink">{nasaBaseline}</p>}
          {frostSummary && <p className="mt-2 text-sm leading-relaxed text-agro-slate">{frostSummary}</p>}
        </section>
      )}

      <WeatherMetricTabs active={metric} onChange={setMetric} labels={metricLabels} />

      <HourlyWeatherChart hours={hours} metric={metric} />

      {days.length > 0 && (
        <WeeklyForecast days={days} selectedDate={activeDay} onSelect={setActiveDay} />
      )}
    </div>
  );
}
