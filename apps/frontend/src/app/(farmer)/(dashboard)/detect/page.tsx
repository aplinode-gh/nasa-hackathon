import type { Metadata } from "next";
import { backendFetch } from "@/lib/backend";
import { getDetectBundle } from "@/lib/i18n/server";
import DetectUpload from "./detect-upload";
import type { FarmOption, ScanHistoryItem } from "./detect-types";

export const metadata: Metadata = {
  title: "Detect — AgroAI",
};

type FarmRow = { id: string; name: string; crops: unknown };
type ScanResponse = { scans: ScanHistoryItem[]; nextCursor: string | null };

export default async function DetectPage() {
  const [bundle, rawFarms, history] = await Promise.all([
    getDetectBundle(),
    backendFetch<FarmRow[]>("/api/farms"),
    backendFetch<ScanResponse>("/api/detect/history?limit=20"),
  ]);

  const farms: FarmOption[] = (rawFarms ?? []).map((farm) => {
    let crops = farm.crops;
    if (typeof crops === "string") {
      try {
        crops = JSON.parse(crops);
      } catch {
        crops = [];
      }
    }
    return {
      id: farm.id,
      name: farm.name,
      crops: Array.isArray(crops) ? crops.join(", ") : String(crops ?? ""),
    };
  });

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
