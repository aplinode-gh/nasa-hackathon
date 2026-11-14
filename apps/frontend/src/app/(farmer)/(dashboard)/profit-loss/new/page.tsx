import type { Metadata } from "next";
import { backendFetch } from "@/lib/backend";
import { CROPS } from "@/lib/farms/constants";
import NewSeasonClient from "./new-season-client";

export const metadata: Metadata = {
  title: "New season — Agropioo",
};

type FarmRow = { id: string; name: string; crops: string[] };

function cropLabel(crop: string): string {
  return crop.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default async function NewSeasonPage() {
  const farms = (await backendFetch<FarmRow[]>("/api/farms")) ?? [];
  const allCrops = CROPS.map((crop) => ({ id: crop, name_en: cropLabel(crop) }));
  const farmCrops = Object.fromEntries(farms.map((farm) => [farm.id, farm.crops ?? []]));

  return (
    <NewSeasonClient
      farms={farms.map(({ crops: _crops, ...rest }) => rest)}
      crops={allCrops}
      farmCrops={farmCrops}
    />
  );
}
