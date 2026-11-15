import type { Metadata } from "next";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import { getPricesBundle } from "@/lib/i18n/server";
import FavouritesClient from "./favourites-client";

export const metadata: Metadata = {
  title: "Favourite Crops — AgroAI",
};

type CropOption = { id: string; name_en: string };

export default async function FavouritesPage() {
  await requireSessionPage();

  const [bundle, optionsRes] = await Promise.all([
    getPricesBundle(),
    backendFetch("/api/prices/options"),
  ]);

  let crops: CropOption[] = [];
  if (optionsRes.ok) {
    try {
      const data = (await optionsRes.json()) as { crops?: CropOption[] };
      crops = data.crops ?? [];
    } catch {
      crops = [];
    }
  }

  return (
    <div className="pt-1">
      <div className="mt-6">
        <FavouritesClient bundle={bundle} crops={crops} />
      </div>
    </div>
  );
}
