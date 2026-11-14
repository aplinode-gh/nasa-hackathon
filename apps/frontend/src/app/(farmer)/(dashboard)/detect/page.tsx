import type { Metadata } from "next";
import { backendFetch } from "@/lib/backend";
import { getDetectBundle } from "@/lib/i18n/server";
import DetectUpload from "./detect-upload";
import type { FarmOption, ScanHistoryItem } from "./detect-types";

export const metadata: Metadata = {
  title: "Detect — Agropioo",
};

type FarmRow = { id: string; name: string; crops: unknown };
type ScanResponse = { scans: ScanHistoryItem[]; nextCursor: string | null };

export default async function DetectPage() {
  const [bundle, rawFarms, history] = await Promise.all([
    getDetectBundle(),
    backendFetch<FarmRow[]>("/api/farms"),
    backendFetch<ScanResponse>("/api/detect/history?limit=20"),
  ]);

  const farms: FarmOption[] = (rawFarms ?? []).map((farm) => ({
    id: farm.id,
    name: farm.name,
    crops: Array.isArray(farm.crops)
      ? farm.crops.join(", ")
      : typeof farm.crops === "string"
        ? farm.crops
        : String(farm.crops ?? ""),
  }));

  const initialScans = history?.scans ?? [];

  return (
    <div className="pt-1">
      <DetectUpload
        bundle={bundle}
        farms={farms}
        initialScans={initialScans}
        nextCursor={history?.nextCursor ?? null}
      />
    </div>
  );
}
