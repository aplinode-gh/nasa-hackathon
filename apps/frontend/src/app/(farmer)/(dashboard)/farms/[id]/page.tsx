import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CloudRainIcon } from "@/components/icons";
import { getFarmsBundle } from "@/lib/i18n/server";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import FarmRecordsSection from "./farm-records-section";

export const metadata: Metadata = {
  title: "Farm details — AgroAI",
};

const healthChip = {
  good: "bg-agro-mint text-agro-canopy",
  watch: "border border-white/30 bg-white/10 text-white",
} as const;

type FarmDetail = Record<string, unknown> & {
  id: string;
  health?: string;
  recent_records?: Record<string, unknown>[];
  lat?: number | null;
  lng?: number | null;
};

export default async function FarmDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireSessionPage();
  const { id } = await params;
  const farm = await backendFetch<FarmDetail>(`/api/farms/${encodeURIComponent(id)}`);
  if (!farm) notFound();

  const bundle = await getFarmsBundle();
  const f = farm as FarmDetail;

  let weather: { temp_c: number | null; condition: string | null } | null = null;
  if (f.lat != null && f.lng != null) {
    weather = await backendFetch<{ temp_c: number | null; condition: string | null }>(
      `/api/weather/current?lat=${encodeURIComponent(String(f.lat))}&lng=${encodeURIComponent(String(f.lng))}`,
    );
  }

  return (
    <div className="space-y-8 pt-1">
      <header className="relative overflow-hidden rounded-3xl bg-agro-forest p-6 text-white sm:p-8">
        <svg className="drift pointer-events-none absolute -end-24 -top-24 h-56 w-56 text-agro-sprout/15" viewBox="0 0 400 400" fill="none" aria-hidden="true">
          <circle cx="200" cy="200" r="164" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 10" />
        </svg>
        <p className="relative font-mono text-xs font-semibold uppercase tracking-[0.22em] text-agro-sprout">
          {bundle.detail.heroEyebrow}
        </p>
        <h1 className="display-heading relative mt-3 font-display text-3xl font-bold tracking-tight sm:text-4xl">
          {f.name as string}
        </h1>
        <div className="relative mt-4 flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.7rem] font-medium ${f.health === 'good' ? healthChip.good : healthChip.watch}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${f.health === 'good' ? 'bg-agro-success' : 'border border-agro-sprout'}`} aria-hidden="true" />
            {f.health === 'good' ? bundle.detail.goodHealth : bundle.detail.needsWatching}
          </span>
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-agro-sprout">
            {Array.isArray(f.crops) ? (f.crops as string[]).join(', ') : String(f.crops)}
          </span>
          <span className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white/75">
            {String(f.acres)} {bundle.unitsAcres}
          </span>
          <span className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white/75">
            {f.district as string}
          </span>
          <span className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white/75">
            {f.location as string}
          </span>
          {weather && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-white/75">
              <CloudRainIcon size={14} /> {weather.temp_c != null ? `${Math.round(weather.temp_c)}°C` : ''} {weather.condition || ''}
            </span>
          )}
        </div>
      </header>

      <FarmRecordsSection
        farmId={f.id as string}
        records={(f.recent_records as Record<string, unknown>[]) || []}
        bundle={bundle}
      />
    </div>
  );
}
