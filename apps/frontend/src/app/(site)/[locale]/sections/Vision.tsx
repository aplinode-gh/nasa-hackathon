import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function Vision({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);

  const pakistanPoints = [
    t("home.vision.pkPoint1").text,
    t("home.vision.pkPoint2").text,
    t("home.vision.pkPoint3").text,
  ];

  const globalPoints = [
    t("home.vision.worldPoint1").text,
    t("home.vision.worldPoint2").text,
    t("home.vision.worldPoint3").text,
  ];

  return (
    <section
      id="vision"
      className="w-full border-t border-agro-clay/60 bg-white px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="max-w-2xl">
          <p className="reveal inline-flex items-center gap-2 rounded-full border border-agro-sprout/70 bg-agro-mint/50 px-3 py-1 text-sm font-medium text-agro-canopy">
            {t("home.vision.eyebrow").text}
          </p>
          <h2 className="display-heading reveal mt-6 font-display text-3xl font-semibold leading-[1.12] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.75rem]">
            {t("home.vision.titleA").text} {t("home.vision.titleB").text}
          </h2>
        </div>

        <div className="reveal mt-14 grid gap-6 lg:grid-cols-12 lg:gap-8">
          <article className="relative overflow-hidden rounded-3xl border border-agro-sprout/70 bg-gradient-to-br from-agro-mint via-white to-agro-stone/40 p-7 shadow-sm sm:p-10 lg:col-span-7">
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-agro-sprout/30 blur-3xl" aria-hidden="true" />
            <div className="relative">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-agro-canopy text-white shadow-sm">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
              </span>
              <h3 className="mt-6 font-display text-2xl font-semibold tracking-tight text-agro-ink sm:text-[1.85rem]">
                {t("home.vision.pkTitle").text}
              </h3>
              <p className="mt-3 max-w-xl text-base leading-relaxed text-agro-slate sm:text-lg">
                {t("home.vision.pkBody").text}
              </p>
              <ul className="mt-8 space-y-3">
                {pakistanPoints.map((point) => (
                  <li key={point} className="flex items-start gap-3 text-sm text-agro-ink sm:text-base">
                    <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-agro-canopy ring-1 ring-agro-sprout/70" aria-hidden="true">
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </span>
                    <span className="leading-relaxed">{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          </article>

          <article className="flex flex-col rounded-3xl border border-agro-forest/30 bg-agro-forest p-7 text-white shadow-[0_24px_60px_-24px_rgba(1,59,31,0.45)] sm:p-10 lg:col-span-5">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-agro-sprout">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.236m0 0A8.959 8.959 0 013 12c0-.778.099-1.533.284-2.253" />
              </svg>
            </span>
            <h3 className="mt-6 font-display text-2xl font-semibold tracking-tight sm:text-[1.85rem]">
              {t("home.vision.worldTitle").text}
            </h3>
            <p className="mt-3 text-base leading-relaxed text-agro-sprout/85 sm:text-lg">
              {t("home.vision.worldBody").text}
            </p>
            <ul className="mt-auto space-y-3 pt-8">
              {globalPoints.map((point) => (
                <li key={point} className="flex items-start gap-3 text-sm text-white/90 sm:text-base">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-agro-leaf" aria-hidden="true" />
                  <span className="leading-relaxed">{point}</span>
                </li>
              ))}
            </ul>
          </article>
        </div>
      </div>
    </section>
  );
}
