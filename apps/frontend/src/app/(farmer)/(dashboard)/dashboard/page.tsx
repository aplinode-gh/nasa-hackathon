import type { Metadata } from "next";
import { getAppLocale, getDashboardBundle } from "@/lib/i18n/server";
import DashboardView from "./dashboard-view";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import type { WidgetCropPrice } from "@/components/prices/dashboard-prices-widget";

export const metadata: Metadata = {
  title: "Dashboard — AgroAI",
  description:
    "Today's advisory, weather, alerts, and every AgroAI tool — one screen that answers kya karoon aaj?",
};

function cropNameField(locale: string): string {
  const allowed = new Set(["en", "ur", "pa", "skr", "ps", "hno", "sd", "bal"]);
  return allowed.has(locale) ? `name_${locale}` : "name_en";
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const emptyView = params.view === "empty";
  const weatherOff = params.weather === "off";
  const appLocale = await getAppLocale();
  const bundle = await getDashboardBundle();
  const session = await requireSessionPage();

  const user = {
    fullName: session.fullName ?? "Farmer",
    email: session.email,
  };

  let allFarms: Array<Record<string, any>> = [];
  try {
    const farmsRes = await backendFetch<any[] | { farms?: any[] }>("/api/farms");
    if (farmsRes) {
      allFarms = Array.isArray(farmsRes) ? farmsRes : farmsRes?.farms ?? [];
    }
  } catch (err) {
    console.error("Error fetching farms for dashboard:", err);
  }

  const totalFarms = allFarms.length;
  const farms = allFarms.slice(0, 3).map((farm) => ({
    ...farm,
    health: (farm.health as "good" | "watch" | undefined) ?? "good",
  }));

  let widgetPrices: WidgetCropPrice[] = [];
  try {
    const [favRes, optionsRes] = await Promise.all([
      backendFetch<{ favourites?: Array<{ crop_id: string }> }>("/api/favourites"),
      backendFetch<{ crops?: Array<Record<string, any>> }>("/api/prices/options"),
    ]);

    let cropIds: string[] = [];
    if (favRes) {
      const favs = (favRes.favourites ?? []) as Array<{ crop_id: string }>;
      cropIds = favs.slice(0, 3).map((f) => f.crop_id);
    }

    let crops: Array<Record<string, any>> = [];
    if (optionsRes) {
      crops = (optionsRes.crops ?? []) as Array<Record<string, any>>;
    }

    if (cropIds.length === 0) {
      cropIds = crops.slice(0, 3).map((c) => String(c.id));
    }

    const nameKey = cropNameField(appLocale);
    widgetPrices = await Promise.all(
      cropIds.map(async (cropId) => {
        const crop = crops.find((c) => String(c.id) === String(cropId));
        const cropName =
          (crop && typeof crop[nameKey] === "string" && crop[nameKey].trim() ? crop[nameKey] : crop?.name_en) ??
          cropId;

        let sparkline: number[] = [];
        try {
          const p = await backendFetch<{ prices?: any[] }>(
            `/api/prices?crop_id=${encodeURIComponent(cropId)}`,
          );
          if (p) {
            const rows = Array.isArray(p.prices) ? p.prices : [];
            sparkline = rows
              .slice(0, 7)
              .map((r: any) => Number(r.modal_price ?? 0))
              .filter((n: number) => Number.isFinite(n));
            if (sparkline.length > 1) sparkline = [...sparkline].reverse();
          }
        } catch {
          sparkline = [];
        }

        const latest = sparkline[sparkline.length - 1] ?? 0;
        const prev = sparkline[sparkline.length - 2] ?? latest;
        const changePct = prev === 0 ? 0 : Math.round(((latest - prev) / prev) * 1000) / 10;

        return {
          crop_id: String(cropId),
          crop_name: String(cropName),
          modal_price: latest,
          change_pct: changePct,
          sparkline,
        } satisfies WidgetCropPrice;
      }),
    );
  } catch (err) {
    console.error("Error fetching dashboard prices widget data:", err);
  }

  return (
    <DashboardView
      variant={emptyView ? "empty" : "default"}
      weatherAvailable={!weatherOff}
      appLocale={appLocale}
      bundle={bundle}
      farms={farms}
      totalFarms={totalFarms}
      user={user}
      widgetPrices={widgetPrices}
    />
  );
}
