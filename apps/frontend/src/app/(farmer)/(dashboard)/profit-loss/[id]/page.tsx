import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { PLSummary } from "@/lib/calculations/profit-loss";
import { backendFetch } from "@/lib/backend";
import SeasonDetailClient from "./season-detail-client";

export const metadata: Metadata = {
  title: "Season details — AgroAI",
};

type SeasonDetail = {
  id: string;
  crop_id: string;
  crop_name?: string;
  season: string;
  year: string;
  acres: number;
  status: string;
  expected_yield: number | null;
  expected_price: number | null;
  actual_yield: number | null;
  actual_price: number | null;
  archived_at: string | null;
  farm_name?: string;
  expenses: Array<Record<string, unknown>>;
  projected_costs: Array<Record<string, unknown>>;
  pl: PLSummary;
  break_even: { yield: string; price: string } | null;
  crop_unit: string;
  actual_revenue: number;
};

export default async function SeasonDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const season = await backendFetch<SeasonDetail>(`/api/profit-loss/${id}`);
  if (!season) notFound();

  return <SeasonDetailClient season={season} />;
}
