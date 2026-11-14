import { getDictionary } from "@/lib/i18n/server";
import { localized } from "@/lib/i18n/localized";
import type { Locale } from "@/lib/i18n/config";

function CardShell({
  code,
  title,
  description,
  included,
  children,
}: {
  code: React.ReactNode;
  title: React.ReactNode;
  description: React.ReactNode;
  included: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <article
      className="reveal flex flex-col rounded-2xl border border-agro-sprout/80 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-agro-canopy/50 hover:shadow-xl sm:p-8"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-agro-canopy">
          {code}
        </p>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-agro-sprout bg-agro-mint px-2.5 py-1 font-mono text-[0.6rem] font-bold uppercase tracking-wide text-agro-forest">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          {included}
        </span>
      </div>
      <h3 className="mt-4 text-lg font-semibold tracking-tight text-agro-ink">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-agro-slate">
        {description}
      </p>
      <div className="mt-6 flex-1">{children}</div>
    </article>
  );
}

export default async function IntelligenceSuite({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  return (
    <section
      id="intelligence"
      className="w-full border-t border-agro-clay/70 bg-white px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-end">
          <div className="lg:col-span-7">
            <p className="eyebrow reveal flex items-center gap-3 text-agro-canopy">
              <span className="inline-block h-px w-8 bg-agro-leaf" aria-hidden="true" />
              {L("feat.intel.eyebrow")}
            </p>
            <h2 className="display-heading reveal mt-5 font-display text-3xl font-medium leading-[1.15] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.9rem]">
              {L("feat.intel.heading")}
            </h2>
          </div>
          <p className="reveal max-w-md leading-relaxed text-agro-slate lg:col-span-4 lg:col-start-9">
            {L("feat.intel.sub")}
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-2">
          {/* Weather-aware advisory */}
          <CardShell
            code={L("feat.intel.weatherCode")}
            title={L("feat.intel.weatherTitle")}
            description={L("feat.intel.weatherDesc")}
            included={L("feat.intel.included")}
          >
            <div
              className="space-y-3 rounded-xl bg-agro-mint/60 p-4 ring-1 ring-agro-sprout/70"
              role="img"
              aria-label={t("feat.intel.weatherMock").text}
            >
              <div className="flex items-start gap-3 rounded-lg border border-agro-warning/50 bg-white px-4 py-3">
                <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-agro-warning/15 text-agro-warning" aria-hidden="true">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15zM9 20.25l-.75 1.5m5.25-1.5l-.75 1.5m4.5-1.5l-.75 1.5" />
                  </svg>
                </span>
                <div>
                  <p className="text-sm font-semibold text-agro-ink">
                    {L("feat.intel.delayIrrigation")}
                  </p>
                  <p className="mt-0.5 text-xs leading-relaxed text-agro-slate">
                    {L("feat.intel.rainNote")}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-white px-4 py-2.5 ring-1 ring-agro-clay">
                <span className="font-mono text-xs text-agro-slate">{L("feat.intel.waterSaved")}</span>
                <span className="font-mono text-sm font-bold text-agro-success">~35%</span>
              </div>
            </div>
          </CardShell>

          {/* Crop recommendation */}
          <CardShell
            code={L("feat.intel.cropCode")}
            title={L("feat.intel.cropTitle")}
            description={L("feat.intel.cropDesc")}
            included={L("feat.intel.included")}
          >
            <ol
              className="space-y-2.5 rounded-xl bg-agro-mint/60 p-4 ring-1 ring-agro-sprout/70"
              role="img"
              aria-label={t("feat.intel.cropMock").text}
            >
              {[
                { rank: "1", cropKey: "feat.intel.crop1", score: 92, pick: true },
                { rank: "2", cropKey: "feat.intel.crop2", score: 78, pick: false },
                { rank: "3", cropKey: "feat.intel.crop3", score: 65, pick: false },
              ].map((row) => (
                <li
                  key={row.rank}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 ${
                    row.pick ? "bg-white ring-2 ring-agro-canopy" : "bg-white ring-1 ring-agro-clay"
                  }`}
                >
                  <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-agro-canopy font-mono text-xs font-bold text-white">
                    {row.rank}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-agro-ink">
                    {L(row.cropKey as Parameters<typeof t>[0])}
                  </span>
                  <div className="hidden w-24 sm:block" aria-hidden="true">
                    <div className="h-1.5 overflow-hidden rounded-full bg-agro-clay">
                      <div className="h-full rounded-full bg-agro-leaf" style={{ width: `${row.score}%` }} />
                    </div>
                  </div>
                  <span className="font-mono text-xs font-bold text-agro-canopy">{row.score}</span>
                </li>
              ))}
            </ol>
          </CardShell>
        </div>
      </div>
    </section>
  );
}
