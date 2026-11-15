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
  const [bundle, farmsData] = await Promise.all([
    getCropsBundle(),
    backendFetch<any>("/api/farms"),
  ]);

  const list = Array.isArray(farmsData) ? farmsData : farmsData?.farms ?? [];
  const farms: Array<{ id: string; name: string; location: string }> = list.map((f: any) => ({
    id: String(f.id),
    name: String(f.name ?? ""),
    location: String(f.location ?? ""),
  }));

  return <CropsClient bundle={bundle} farms={farms} />;
}
