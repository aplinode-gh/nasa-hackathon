import type { Metadata } from "next";
import Link from "next/link";
import { getCropsBundle } from "@/lib/i18n/server";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import CropsClient from "../crops-client";

interface PageProps {
  params: Promise<{ request_id: string }>;
}

export const metadata: Metadata = {
  title: "Recommendation detail — AgroAI",
};

export default async function CropRecommendationDetailPage({ params }: PageProps) {
  await requireSessionPage();
  const bundle = await getCropsBundle();
  const { request_id } = await params;

  let request: Record<string, unknown> | null = null;
  let recommendations: Array<any> = [];

  try {
    const res = await backendFetch(`/api/crops/${encodeURIComponent(request_id)}`);
    if (res.ok) {
      const data = await res.json();
      request = data?.request ?? null;
      recommendations = data?.recommendations ?? [];
    }
  } catch {
    // best-effort render; client shows not-found state
  }

  if (!request) {
    return (
      <div className="rounded-2xl border border-agro-sprout bg-white p-8 text-center">
        <p className="text-sm text-agro-slate">{bundle.errors.notFound}</p>
      </div>
    );
  }

  const initialRequestData = {
    soilType: String(request.soil_type ?? ""),
    targetSeason: String(request.target_season ?? ""),
  };

  return (
    <div className="space-y-6 pt-1">
      <div className="flex items-center gap-2">
        <Link
          href="/crops"
          className="inline-flex min-h-11 items-center gap-1 rounded-md text-sm font-semibold text-agro-canopy underline-offset-4 hover:underline"
        >
          ← {bundle.detail.back}
        </Link>
      </div>

      <div className="rounded-2xl border border-agro-sprout bg-white p-5 sm:p-6">
        <h1 className="font-display text-2xl font-bold text-agro-forest sm:text-3xl">{bundle.detail.title}</h1>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-agro-slate">Season</p>
            <p className="mt-1 text-sm font-medium text-agro-ink">{String(request.target_season ?? "")}</p>
          </div>
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-agro-slate">Year</p>
            <p className="mt-1 text-sm font-medium text-agro-ink">{String(request.target_year ?? "")}</p>
          </div>
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-agro-slate">Soil</p>
            <p className="mt-1 text-sm font-medium text-agro-ink">{String(request.soil_type ?? "")}</p>
          </div>
        </div>
      </div>

      <CropsClient
        bundle={bundle}
        farms={[]}
        initialRecommendations={recommendations}
        initialRequest={initialRequestData}
      />
    </div>
  );
}
