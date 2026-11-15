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

async function safeJson<T>(res: Response, fallback: T): Promise<T> {
  if (!res.ok) return fallback;
  try {
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

export default async function PricesPage() {
  await requireSessionPage();

  const [bundle, optionsRes, farmsRes, pricesRes] = await Promise.all([
    getPricesBundle(),
    backendFetch("/api/prices/options"),
    backendFetch("/api/farms"),
    backendFetch("/api/prices"),
  ]);

  const options = await safeJson<{ crops?: CropOption[]; mandis?: MandiOption[] }>(optionsRes, {});
  const farmsData = await safeJson<any>(farmsRes, []);
  const initial = await safeJson<PricesResponse>(pricesRes, {
    district: null,
    is_fallback_hub: false,
    prices: [],
  });

  const farms = (Array.isArray(farmsData) ? farmsData : farmsData?.farms ?? []) as FarmOption[];

  return (
    <div className="pt-1">
      <div className="mt-6">
        <PricesClient
          bundle={bundle}
          crops={options.crops ?? []}
          mandis={options.mandis ?? []}
          farms={farms}
          initial={initial}
        />
      </div>
    </div>
  );
}
