import type { Metadata } from "next";
import Link from "next/link";
import PageHeader from "@/components/shell/page-header";
import { PlusIcon } from "@/components/icons";
import { backendFetch } from "@/lib/backend";
import SeasonCard from "@/components/profit-loss/season-card";

export const metadata: Metadata = {
  title: "Profit / Loss — Agropioo",
};

type SeasonRow = {
  id: string;
  crop_name: string;
  farm_name: string;
  season: string;
  year: string;
  acres: number;
  status: string;
  pl: { netProfitLoss: number; roi: number | null };
};

export default async function ProfitLossPage() {
  const data = await backendFetch<{ seasons: SeasonRow[] }>("/api/profit-loss");
  const seasons = (data?.seasons ?? []).map((season) => ({
    ...season,
    crop_name: season.crop_name ?? "",
    farm_name: season.farm_name ?? "",
  }));

  return (
    <div className="pt-1">
      <PageHeader
        eyebrow="Financial cockpit"
        title="Profit / Loss"
        description="Track your season-level costs, revenue, and profitability."
        action={
          <Link
            href="/profit-loss/new"
            className="inline-flex h-11 items-center gap-2 rounded-lg bg-agro-canopy px-4 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:bg-agro-forest hover:shadow-md"
          >
            <PlusIcon className="h-4 w-4" />
            New season
          </Link>
        }
      />

      {seasons.length === 0 ? (
        <div className="mt-10 rounded-2xl border border-agro-sprout bg-white p-8 text-center">
          <p className="text-sm text-agro-slate">No seasons yet. Start your first season to track costs and profits.</p>
          <Link href="/profit-loss/new" className="mt-4 inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-agro-canopy px-5 text-sm font-semibold text-white">
            Start a new season
          </Link>
        </div>
      ) : (
        <ul className="mt-6 grid gap-3 sm:gap-4 lg:grid-cols-2">
          {seasons.map((season) => (
            <li key={season.id}>
              <SeasonCard season={season} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
