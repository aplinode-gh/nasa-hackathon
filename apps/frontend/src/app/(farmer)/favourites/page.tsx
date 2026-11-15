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

  const [bundle, options] = await Promise.all([
    getPricesBundle(),
    backendFetch<{ crops?: CropOption[] }>("/api/prices/options"),
  ]);

  return (
    <div className="pt-1">
      <div className="mt-6">
        <FavouritesClient bundle={bundle} crops={options?.crops ?? []} />
      </div>
    </div>
  );
}
