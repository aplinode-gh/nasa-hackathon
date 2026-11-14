import Image from "next/image";

import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import { formatNumber } from "@/lib/i18n/format";
import type { Locale } from "@/lib/i18n/config";

export default async function Hero({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const readings = [
    {
      label: L("home.hero.readingCrop"),
      value: formatNumber(92, locale),
      suffix: "%",
      note: L("home.hero.noteExcellent"),
    },
    {
      label: L("home.hero.readingWeather"),
      value: formatNumber(24, locale),
      suffix: "°C",
      note: L("home.hero.noteClearSky"),
    },
    {
      label: L("home.hero.readingSoil"),
      value: formatNumber(65, locale),
      suffix: "%",
      note: L("home.hero.noteOptimal"),
    },
  ];

  return (
    <section
      id="top"
      className="relative isolate w-full overflow-hidden bg-gradient-to-b from-white via-agro-mint/35 to-white px-4 pb-16 pt-10 sm:px-6 sm:pb-20 sm:pt-14 lg:px-8 lg:pb-24 lg:pt-20"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[32rem] bg-[radial-gradient(60%_60%_at_20%_10%,rgba(63,136,57,0.12),transparent_60%),radial-gradient(45%_45%_at_85%_20%,rgba(193,216,193,0.45),transparent_70%)]"
        aria-hidden="true"
      />

      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-16">
        <div className="flex min-w-0 flex-col items-start text-start">
          <p className="rise inline-flex items-center gap-2 rounded-full border border-agro-sprout/80 bg-white/80 px-3.5 py-1.5 text-sm font-medium text-agro-canopy shadow-sm backdrop-blur-sm">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-agro-leaf" aria-hidden="true" />
            {L("home.hero.eyebrow")}
          </p>

          <h1
            className="display-heading rise mt-6 max-w-3xl font-display text-[2.5rem] font-semibold leading-[1.06] tracking-tight text-agro-ink sm:text-5xl lg:text-[4rem] xl:text-[4.4rem]"
            style={{ "--rise-delay": "0.08s" } as React.CSSProperties}
          >
            {L("home.hero.titleLead")}{" "}
            <span className="text-agro-canopy">{L("home.hero.titleAccent")}</span>
          </h1>

          <p
            className="rise mt-6 max-w-xl text-base leading-relaxed text-agro-slate sm:text-lg"
            style={{ "--rise-delay": "0.16s" } as React.CSSProperties}
          >
            {L("home.hero.subtitle")}
          </p>

          <div
            className="rise mt-8 flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center"
            style={{ "--rise-delay": "0.24s" } as React.CSSProperties}
          >
            <a
              href="#get-started"
              className="inline-flex h-12 cursor-pointer items-center justify-center rounded-xl bg-agro-canopy px-7 text-sm font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-agro-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-canopy active:bg-agro-forest"
            >
              {L("nav.getEarlyAccess")}
            </a>
            <a
              href="#journey"
              className="inline-flex h-12 cursor-pointer items-center justify-center rounded-xl border border-agro-sprout bg-white px-7 text-sm font-semibold text-agro-forest shadow-sm transition-colors duration-200 hover:border-agro-canopy hover:bg-agro-mint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-canopy"
            >
              {L("home.hero.ctaSecondary")}
            </a>
          </div>

          <div
            className="rise mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-agro-slate"
            style={{ "--rise-delay": "0.3s" } as React.CSSProperties}
          >
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-agro-leaf" aria-hidden="true" />
              {L("common.builtForPakistan")}
            </span>
            <span className="hidden h-4 w-px bg-agro-clay sm:inline-block" aria-hidden="true" />
            <span className="text-agro-slate/90">{L("home.hero.eyebrow")}</span>
          </div>

          <div
            className="rise mt-10 grid w-full max-w-xl grid-cols-1 gap-3 sm:grid-cols-3"
            style={{ "--rise-delay": "0.36s" } as React.CSSProperties}
          >
            {readings.map((reading, index) => (
              <div
                key={index}
                className="rounded-2xl border border-agro-clay/80 bg-white/90 p-4 shadow-sm backdrop-blur-sm transition-shadow duration-200 hover:shadow-md"
              >
                <p className="text-xs font-medium text-agro-slate">{reading.label}</p>
                <p className="mt-2 flex items-baseline gap-1 font-display text-2xl font-semibold tracking-tight text-agro-ink">
                  <span>{reading.value}</span>
                  <span className="text-base font-medium text-agro-canopy">{reading.suffix}</span>
                </p>
                <p className="mt-1 text-xs font-medium text-agro-canopy">{reading.note}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-xl lg:max-w-none">
          <div className="relative overflow-hidden rounded-[2rem] border border-agro-clay/70 bg-white shadow-[0_24px_60px_-24px_rgba(1,59,31,0.25)]">
            <div className="absolute inset-0 bg-gradient-to-br from-agro-mint/70 via-white to-agro-stone/60" aria-hidden="true" />
            <div className="relative aspect-[4/5] w-full sm:aspect-[5/6] lg:aspect-[4/5]">
              <Image
                src="/hero-farmer.svg"
                alt={t("home.hero.imageAlt").text}
                fill
                sizes="(max-width: 1024px) 100vw, 42vw"
                className="object-cover object-center"
                priority
              />
            </div>

            <div className="pointer-events-none absolute inset-x-4 bottom-4 z-10 hidden rounded-2xl border border-white/70 bg-white/85 p-4 shadow-lg backdrop-blur-md sm:block">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-[0.08em] text-agro-slate">
                    {L("home.hero.readingCrop")}
                  </p>
                  <p className="mt-1 font-display text-xl font-semibold text-agro-ink">
                    {formatNumber(92, locale)}% <span className="text-sm font-medium text-agro-canopy">{L("home.hero.noteExcellent")}</span>
                  </p>
                </div>
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-agro-mint text-agro-canopy ring-1 ring-agro-sprout/70">
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          <div className="pointer-events-none absolute -right-6 -top-6 hidden h-28 w-28 rounded-full border border-agro-sprout/50 bg-white/50 blur-[1px] lg:block" aria-hidden="true" />
          <div className="pointer-events-none absolute -bottom-8 -left-4 hidden h-24 w-24 rounded-full bg-agro-sprout/30 blur-2xl lg:block" aria-hidden="true" />
        </div>
      </div>
    </section>
  );
}
