import type { Metadata } from "next";
import { getCropsBundle } from "@/lib/i18n/server";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import CropsClient from "./crops-client";

export const metadata: Metadata = {
  title: "Crop recommendation — AgroAI",
};

export default async function CropsPage() {
  await requireSessionPage();
  const [bundle, farmsRes] = await Promise.all([
    getCropsBundle(),
    backendFetch("/api/farms"),
  ]);

  let farms: Array<{ id: string; name: string; location: string }> = [];
  if (farmsRes.ok) {
    try {
      const data = await farmsRes.json();
      const list = Array.isArray(data) ? data : data?.farms ?? [];
      farms = list.map((f: any) => ({
        id: String(f.id),
        name: String(f.name ?? ""),
        location: String(f.location ?? ""),
      }));
    } catch {
      farms = [];
    }
  }

  return <CropsClient bundle={bundle} farms={farms} />;
}
