import type { Metadata } from "next";
import PageHeader from "@/components/shell/page-header";
import { getFarmsBundle } from "@/lib/i18n/server";
import { requireSessionPage } from "@/lib/auth/guards";
import { backendFetch } from "@/lib/backend";
import FarmRecordItem from "./farm-record-item";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Farm records — AgroAI",
};

export default async function FarmRecordsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireSessionPage();
  const { id } = await params;
  let records: Array<Record<string, unknown>> = [];
  try {
    const res = await backendFetch(`/api/farms/${encodeURIComponent(id)}/records?limit=100`);
    if (res.ok) {
      const data = await res.json();
      records = Array.isArray(data) ? data : data?.records ?? [];
    }
  } catch (err) {
    console.error("Error fetching farm records:", err);
  }

  const bundle = await getFarmsBundle();

  const recordTypeLabel: Record<string, string> = {
    irrigation: bundle.records.types.irrigation,
    fertilizer: bundle.records.types.fertilizer,
    pesticide: bundle.records.types.pesticide,
    disease: bundle.records.types.disease,
    harvest: bundle.records.types.harvest,
    sowing: "Sowing",
    planting: "Planting",
  };

  return (
    <div className="pt-1">
      <PageHeader
        eyebrow={bundle.records.eyebrow}
        title={bundle.records.farmRecords.heading}
        description={bundle.records.farmRecords.description}
      />

      {records.length === 0 ? (
        <div className="mt-6 rounded-xl border-dashed border-agro-sprout bg-agro-mint px-4 py-6 text-center">
          <p className="font-mono text-xs tracking-wide text-agro-slate">
            No records yet. Log your first field event.
          </p>
          <Link
            href={`/records/new?farm=${id}`}
            className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg bg-agro-canopy px-5 text-sm font-semibold text-white transition-colors hover:bg-agro-forest"
          >
            {bundle.detail.logFieldEvent}
          </Link>
        </div>
      ) : (
        <ol className="mt-6 space-y-3">
          {records.map((record, index) => (
            <FarmRecordItem
              key={String(record.id ?? index)}
              record={record}
              index={index}
              total={records.length}
              typeLabel={recordTypeLabel[String(record.type)] || String(record.type ?? "")}
            />
          ))}
        </ol>
      )}
    </div>
  );
}
