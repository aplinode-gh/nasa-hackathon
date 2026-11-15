import type { Metadata } from "next";
import PageHeader from "@/components/shell/page-header";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import { getWeatherBundle } from "@/lib/i18n/server";
import { type GrowthStage, type Severity } from "@/lib/weather/advisory";
import FarmSelector from "@/components/weather/FarmSelector";
import HistoryList, { type HistoryItem } from "@/components/weather/HistoryList";

export const metadata: Metadata = { title: "Advisory history — AgroAI" };

type FarmRow = { id: string; name: string; primary_crop: string | null; crops: string[] | string; location: string; district: string };

function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

export default async function WeatherHistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  await requireSessionPage();
  const bundle = await getWeatherBundle();

  let farmList: FarmRow[] = [];
  try {
    const data = await backendFetch<any>("/api/farms");
    farmList = (Array.isArray(data) ? data : data?.farms ?? []) as FarmRow[];
  } catch {
    farmList = [];
  }

  const params = await searchParams;
  const requested = typeof params.farm === "string" ? params.farm : null;
  const selected = farmList.find((f) => String(f.id) === requested) ?? farmList[0] ?? null;

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

  if (!selected) {
    return (
      <div className="pt-1">
        <PageHeader eyebrow={bundle.eyebrow} title={bundle.historyTitle} description={bundle.historySubtitle} />
        <section className="mt-5 rounded-3xl border border-agro-sprout bg-white p-6 text-center">
          <h2 className="text-lg font-semibold text-agro-forest">{bundle.registerTitle}</h2>
          <p className="mt-1 text-sm text-agro-slate">{bundle.registerBody}</p>
        </section>
      </div>
    );
  }

  let rows: HistoryItem[] = [];
  let nextCursor: string | null = null;
  try {
    const data = await backendFetch<{ items?: HistoryItem[]; next_cursor?: string | null }>(
      `/api/weather/history?farm_id=${encodeURIComponent(String(selected.id))}&limit=20`,
    );
    rows = (data?.items ?? []) as HistoryItem[];
    nextCursor = data?.next_cursor ?? null;
  } catch {
    rows = [];
  }

  const farmOptions = farmList.map((f) => {
    const crops = Array.isArray(f.crops) ? f.crops : [];
    const primary = f.primary_crop ?? crops[0] ?? "";
    return {
      id: String(f.id),
      name: String(f.name ?? ""),
      cropLabel: capitalize(String(primary)),
      location: String(f.location ?? ""),
      district: String(f.district ?? ""),
    };
  });

  return (
    <div className="pt-1">
      <PageHeader eyebrow={bundle.eyebrow} title={bundle.historyTitle} description={bundle.historySubtitle} />
      <div className="mt-5">
        <FarmSelector farms={farmOptions} selectedId={String(selected.id)} label={bundle.farmSelectorLabel} />
      </div>

      <HistoryList
        initialItems={rows}
        initialCursor={nextCursor}
        farmId={String(selected.id)}
        strings={{
          date: bundle.historyDate,
          severity: bundle.historySeverity,
          status: bundle.historyStatus,
          statusNew: bundle.historyStatusNew,
          statusSeen: bundle.historyStatusSeen,
          statusActed: bundle.historyStatusActed,
          loadMore: bundle.historyLoadMore,
          empty: bundle.historyEmpty,
        }}
        severityLabels={severityLabels}
        stageLabels={stageLabels}
      />
    </div>
  );
}
