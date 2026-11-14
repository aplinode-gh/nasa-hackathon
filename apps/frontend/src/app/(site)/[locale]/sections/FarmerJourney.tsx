import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function FarmerJourney({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const steps = [
    { title: L("home.journey.step1Title"), description: L("home.journey.step1Body") },
    { title: L("home.journey.step2Title"), description: L("home.journey.step2Body") },
    { title: L("home.journey.step3Title"), description: L("home.journey.step3Body") },
    { title: L("home.journey.step4Title"), description: L("home.journey.step4Body") },
    { title: L("home.journey.step5Title"), description: L("home.journey.step5Body") },
    { title: L("home.journey.step6Title"), description: L("home.journey.step6Body") },
  ];

  return (
    <section
      id="journey"
      className="w-full border-t border-agro-clay/60 bg-agro-stone/30 px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto max-w-3xl text-center">
          <p className="reveal inline-flex items-center gap-2 rounded-full border border-agro-sprout/70 bg-white px-3 py-1 text-sm font-medium text-agro-canopy shadow-sm">
            {L("home.journey.eyebrow")}
          </p>
          <h2 className="display-heading reveal mt-6 font-display text-3xl font-semibold leading-[1.12] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.75rem]">
            {L("home.journey.title")}
          </h2>
          <p className="reveal mt-5 text-base leading-relaxed text-agro-slate sm:text-lg">
            {L("home.journey.subtitle")}
          </p>
        </div>

        <ol className="mx-auto mt-14 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {steps.map((step, index) => (
            <li
              key={index}
              className="reveal group relative flex h-full flex-col rounded-3xl border border-agro-clay/80 bg-white p-6 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-7"
            >
              <div className="flex items-start justify-between gap-4">
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-agro-mint text-sm font-semibold text-agro-canopy ring-1 ring-agro-sprout/70">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {index < steps.length - 1 && (
                  <span
                    className="mt-5 hidden h-px flex-1 bg-gradient-to-r from-agro-sprout/70 to-transparent lg:block"
                    aria-hidden="true"
                  />
                )}
              </div>
              <h3 className="mt-5 font-display text-xl font-semibold tracking-tight text-agro-ink">
                {step.title}
              </h3>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-agro-slate sm:text-base">
                {step.description}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
