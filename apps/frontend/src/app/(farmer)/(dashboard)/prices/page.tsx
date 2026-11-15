import type { Metadata } from "next";
import { requireSessionPage } from "@/lib/auth/guards";
import { getPricesBundle } from "@/lib/i18n/server";
import { backendFetch } from "@/lib/backend";
import PricesClient from "./prices-client";

export const metadata: Metadata = {
  title: "Mandi Prices — AgroAI",
};

type CropOption = { id: string; name_en: string };
type MandiOption = { id: string; name_en: string };
type FarmOption = { id: string; name: string; district?: string; crops?: string };

type PricesResponse = {
  district: string | null;
  is_fallback_hub: boolean;
  prices: any[];
};

export default async function PricesPage() {
  await requireSessionPage();

  const [bundle, options, farmsData, initialData] = await Promise.all([
    getPricesBundle(),
    backendFetch<{ crops?: CropOption[]; mandis?: MandiOption[] }>("/api/prices/options"),
    backendFetch<any>("/api/farms"),
    backendFetch<PricesResponse>("/api/prices"),
  ]);

  const farms = (Array.isArray(farmsData) ? farmsData : farmsData?.farms ?? []) as FarmOption[];
  const initial: PricesResponse = initialData ?? { district: null, is_fallback_hub: false, prices: [] };

  return (
    <div className="pt-1">
      <div className="mt-6">
        <PricesClient
          bundle={bundle}
          crops={options?.crops ?? []}
          mandis={options?.mandis ?? []}
          farms={farms}
          initial={initial}
        />
      </div>
    </div>
  );
}
