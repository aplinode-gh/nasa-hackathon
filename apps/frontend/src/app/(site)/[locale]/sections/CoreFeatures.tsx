import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

// All seven constitutional local languages, incl. Sindhi (FR-25).
const languages = [
  { name: "اردو", lang: "ur" },
  { name: "پنجابی", lang: "pa-Arab" },
  { name: "سنڌي", lang: "sd" },
  { name: "سرائیکی", lang: "skr" },
  { name: "پښتو", lang: "ps" },
  { name: "بلوچی", lang: "bal" },
  { name: "ہندکو", lang: "hno" },
];

const recordRows = [
  { date: "12 Aug", activityKey: "home.features.record1Activity", detailKey: "home.features.record1Detail" },
  { date: "09 Aug", activityKey: "home.features.record2Activity", detailKey: "home.features.record2Detail" },
  { date: "05 Aug", activityKey: "home.features.record3Activity", detailKey: "home.features.record3Detail" },
] as const;

const forecast = [
  { dayKey: "home.features.dayMon", condition: "sun" },
  { dayKey: "home.features.dayTue", condition: "sun" },
  { dayKey: "home.features.dayWed", condition: "cloud" },
  { dayKey: "home.features.dayThu", condition: "rain", advisory: true },
  { dayKey: "home.features.dayFri", condition: "sun" },
] as const;

const cardClass =
  "reveal flex h-full flex-col rounded-3xl border border-agro-clay/80 bg-white p-6 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-8";

function WeatherGlyph({ kind }: { kind: string }) {
  if (kind === "sun") {
    return (
      <svg className="h-4 w-4 text-agro-leaf" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
      </svg>
    );
  }
  if (kind === "rain") {
    return (
      <svg className="h-4 w-4 text-agro-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15zM9 20.25l-.75 1.5m5.25-1.5l-.75 1.5m4.5-1.5l-.75 1.5" />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4 text-agro-slate" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
    </svg>
  );
}

function CardIcon({ path }: { path: string }) {
  return (
    <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-agro-mint text-agro-canopy ring-1 ring-agro-sprout/70">
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d={path} />
      </svg>
    </span>
  );
}

export default async function CoreFeatures({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  return (
    <section
      id="features"
      className="w-full border-t border-agro-clay/60 bg-agro-stone/40 px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-end lg:gap-12">
          <div className="min-w-0 lg:col-span-7">
            <p className="reveal inline-flex items-center gap-2 rounded-full border border-agro-sprout/70 bg-white px-3 py-1 text-sm font-medium text-agro-canopy shadow-sm">
              {L("home.features.eyebrow")}
            </p>
            <h2 className="display-heading reveal mt-6 max-w-3xl font-display text-3xl font-semibold leading-[1.12] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.75rem]">
              {L("home.features.titleA")} {L("home.features.titleB")}
            </h2>
          </div>
          <p className="reveal max-w-md text-base leading-relaxed text-agro-slate sm:text-lg lg:col-span-5">
            {L("home.features.subtitle")}
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {/* AI advisor — hero card with example conversation */}
          <article className={`${cardClass} md:col-span-2`}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-4">
                <CardIcon path="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-agro-canopy">
                    {L("home.features.advisorModule")}
                  </p>
                  <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-agro-ink sm:text-2xl">
                    {L("home.features.advisorTitle")}
                  </h3>
                  <p className="mt-1 text-sm text-agro-slate">
                    {L("home.features.advisorTopics")}
                  </p>
                </div>
              </div>
              <span className="inline-flex shrink-0 items-center rounded-full border border-agro-sprout bg-agro-mint/70 px-3 py-1 text-xs font-semibold text-agro-canopy">
                {L("home.features.advisorBadge")}
              </span>
            </div>

            <div
              className="mt-6 flex-1 space-y-4 rounded-2xl border border-agro-clay/70 bg-agro-stone/50 p-4 sm:p-6"
              role="img"
              aria-label={t("home.features.advisorMockAria").text}
            >
              <div className="flex justify-end">
                <div className="max-w-[88%] rounded-2xl rounded-br-md bg-agro-canopy px-4 py-3 text-sm leading-relaxed text-white shadow-sm sm:max-w-[72%]">
                  {L("home.features.advisorUserMsg")}
                </div>
              </div>

              <div className="flex justify-start">
                <div className="max-w-[94%] rounded-2xl rounded-bl-md border border-agro-clay/80 bg-white px-4 py-3.5 text-sm leading-relaxed text-agro-ink shadow-sm sm:max-w-[82%]">
                  <p className="font-semibold text-agro-forest">
                    {L("home.features.advisorReplyTitle")}
                  </p>
                  <ul className="mt-2 space-y-2">
                    <li className="flex gap-2.5">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-agro-leaf" aria-hidden="true" />
                      <span><strong className="font-semibold text-agro-ink">{L("home.features.advisorReplyCause1")}</strong> {L("home.features.advisorReplyCause1Rest")}</span>
                    </li>
                    <li className="flex gap-2.5">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-agro-leaf" aria-hidden="true" />
                      <span><strong className="font-semibold text-agro-ink">{L("home.features.advisorReplyCause2")}</strong> {L("home.features.advisorReplyCause2Rest")}</span>
                    </li>
                  </ul>
                  <p className="mt-3 text-agro-slate">
                    {L("home.features.advisorReplyFooter")}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-xl border border-agro-clay/80 bg-white px-4 py-3 shadow-sm">
                <span className="h-2 w-2 shrink-0 rounded-full bg-agro-leaf/70" aria-hidden="true" />
                <span className="w-full truncate text-sm text-agro-slate">
                  {L("home.features.advisorInputPlaceholder")}
                </span>
              </div>
            </div>

            <p className="mt-5 text-sm leading-relaxed text-agro-slate">
              {L("home.features.advisorFooter")}
            </p>
          </article>

          {/* Digital farm record */}
          <article className={cardClass}>
            <CardIcon path="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-agro-canopy">
              {L("home.features.recordsModule")}
            </p>
            <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-agro-ink">
              {L("home.features.recordsTitle")}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-agro-slate">
              {L("home.features.recordsDesc")}
            </p>

            <ul className="mt-6 flex-1 divide-y divide-agro-clay/70 overflow-hidden rounded-2xl border border-agro-clay/70 bg-agro-stone/30">
              {recordRows.map((row) => (
                <li key={row.date} className="flex items-center justify-between gap-3 px-4 py-3">
                  <span className="shrink-0 text-xs font-medium text-agro-slate">{row.date}</span>
                  <span className="min-w-0 flex-1 text-sm font-medium text-agro-ink">{L(row.activityKey)}</span>
                  <span className="max-w-[8rem] text-right text-xs text-agro-slate sm:max-w-none">{L(row.detailKey)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs font-medium text-agro-canopy">
              {L("home.features.recordsCropTag")}
            </p>
          </article>

          {/* Local language */}
          <article className={cardClass}>
            <CardIcon path="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.233.038 3.334.114M9 5.25V3m3.334 2.364C11.176 10.658 7.69 15.08 3 17.502m9.334-12.138c.896.061 1.785.147 2.666.257m-4.589 8.495a18.023 18.023 0 01-3.827-5.802" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-agro-canopy">
              {L("home.features.languageModule")}
            </p>
            <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-agro-ink">
              {L("home.features.languageTitle")}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-agro-slate">
              {L("home.features.languageDesc")}
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              {languages.map((lang) => (
                <span
                  key={lang.lang}
                  className="rounded-full border border-agro-sprout/80 bg-white px-3.5 py-1.5 text-base leading-none text-agro-forest shadow-sm"
                  dir="rtl"
                  lang={lang.lang}
                >
                  {lang.name}
                </span>
              ))}
            </div>
          </article>

          {/* Weather-aware guidance */}
          <article className={`${cardClass} md:col-span-2`}>
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-md">
                <CardIcon path="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
                <p className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-agro-canopy">
                  {L("home.features.weatherModule")}
                </p>
                <h3 className="mt-1 font-display text-xl font-semibold tracking-tight text-agro-ink sm:text-2xl">
                  {L("home.features.weatherTitle")}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-agro-slate sm:text-base">
                  {L("home.features.weatherDesc")}
                </p>
              </div>

              <div
                className="w-full min-w-0 flex-1 lg:max-w-md"
                role="img"
                aria-label={t("home.features.weatherMockAria").text}
              >
                <ol className="grid grid-cols-5 gap-2">
                  {forecast.map((day) => (
                    <li
                      key={day.dayKey}
                      className={`flex flex-col items-center gap-2 rounded-2xl px-1 py-3 text-center ${
                        "advisory" in day && day.advisory
                          ? "border border-agro-canopy/40 bg-agro-mint shadow-sm"
                          : "border border-agro-clay/70 bg-white"
                      }`}
                    >
                      <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-agro-slate">
                        {t(day.dayKey).text}
                      </span>
                      <WeatherGlyph kind={day.condition} />
                      <span
                        className={`min-h-[1.5rem] text-[0.6rem] font-semibold uppercase leading-tight tracking-wide ${
                          "advisory" in day && day.advisory ? "text-agro-forest" : "text-transparent"
                        }`}
                      >
                        {"advisory" in day && day.advisory ? (
                          <>
                            <span className="sm:hidden">!</span>
                            <span className="hidden sm:inline">{t("home.features.holdSpray").text}</span>
                          </>
                        ) : (
                          "·"
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
                <p className="mt-3 flex items-center gap-2 text-xs text-agro-slate">
                  <span className="inline-block h-2.5 w-2.5 rounded-md border border-agro-canopy/40 bg-agro-mint" aria-hidden="true" />
                  {L("home.features.weatherLegend")}
                </p>
              </div>
            </div>
          </article>
        </div>

        <a
          href="#matrix"
          className="reveal mt-10 inline-flex items-center gap-2 rounded-full border border-agro-sprout bg-white px-4 py-2 text-sm font-semibold text-agro-canopy shadow-sm transition-colors duration-200 hover:border-agro-canopy hover:bg-agro-mint hover:text-agro-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-canopy"
        >
          <span>{L("home.features.moreLink")}</span>
          <svg className="h-4 w-4 rtl:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m0 0l-6-6m6 6l6-6" />
          </svg>
        </a>
      </div>
    </section>
  );
}
