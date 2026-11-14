import { backendFetch } from "@/lib/backend";
import { getPestBundle } from "@/lib/i18n/server";
import PestPageClient from "@/components/pest/PestPageClient";
import Link from "next/link";

export const dynamic = "force-dynamic";

type FarmRow = {
  id: string;
  name: string;
  district: string;
  lat: number;
  lng: number;
  crops: unknown;
  growth_stages: unknown;
  primary_crop: string | null;
};

function parseList(value: unknown): string[] {
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

function parseStages(value: unknown): Record<string, string> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, stage]) => [key, String(stage)]));
  }
  if (typeof value === "string") {
    try {
      return parseStages(JSON.parse(value));
    } catch {
      return {};
    }
  }
  return {};
}

export default async function PestPage() {
  const bundle = await getPestBundle();
  const rawFarms = (await backendFetch<FarmRow[]>("/api/farms")) ?? [];
  const farms = rawFarms.map((farm) => ({
    ...farm,
    crops: parseList(farm.crops),
    growth_stages: parseStages(farm.growth_stages),
  }));

  if (farms.length === 0) {
    return (
      <div className="rounded-2xl border border-agro-sprout bg-white p-6">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.22em] text-agro-canopy">
          {bundle.eyebrow}
        </p>
        <h1 className="display-heading mt-2 font-display text-3xl font-semibold leading-tight tracking-tight text-agro-forest">
          {bundle.pageTitle}
        </h1>
        <div className="mt-6 text-center">
          <p className="text-sm text-agro-slate">{bundle.noFarmsTitle}</p>
          <p className="mt-1 text-sm text-agro-slate">{bundle.noFarmsBody}</p>
          <Link
            href="/farms/new"
            className="mt-4 inline-flex min-h-12 items-center justify-center rounded-xl bg-agro-canopy px-5 text-sm font-semibold text-white transition-colors hover:bg-agro-forest"
          >
            {bundle.addFarm}
          </Link>
        </div>
      </div>
    );
  }

  return <PestPageClient bundle={bundle} farms={farms} />;
}
