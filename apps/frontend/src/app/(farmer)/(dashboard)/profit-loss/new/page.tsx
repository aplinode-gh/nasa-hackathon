import type { Metadata } from "next";
import { backendFetch } from "@/lib/backend";
import { CROPS } from "@/lib/farms/constants";
import NewSeasonClient from "./new-season-client";

export const metadata: Metadata = {
  title: "New season — AgroAI",
};

type FarmRow = { id: string; name: string; crops: unknown };

function cropLabel(crop: string): string {
  return crop.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseCrops(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  }
  return [];
}

export default async function NewSeasonPage() {
  const rawFarms = (await backendFetch<FarmRow[]>("/api/farms")) ?? [];
  const farms = rawFarms.map((farm) => ({ id: farm.id, name: farm.name, crops: parseCrops(farm.crops) }));
  const allCrops = CROPS.map((crop) => ({ id: crop, name_en: cropLabel(crop) }));
  const farmCrops = Object.fromEntries(farms.map((farm) => [farm.id, farm.crops]));

  return (
    <NewSeasonClient
      farms={farms.map(({ crops: _crops, ...rest }) => rest)}
      crops={allCrops}
      farmCrops={farmCrops}
    />
  );
}
