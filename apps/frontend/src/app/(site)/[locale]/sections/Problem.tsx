import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function Problem({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const problems = [
    {
      title: L("home.problem.item1Title"),
      description: L("home.problem.item1Body"),
    },
    {
      title: L("home.problem.item2Title"),
      description: L("home.problem.item2Body"),
    },
    {
      title: L("home.problem.item3Title"),
      description: L("home.problem.item3Body"),
    },
  ];

  return (
    <section
      id="why"
      className="relative w-full overflow-hidden bg-agro-forest px-4 py-20 text-white sm:px-6 lg:px-8 lg:py-28"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(50%_40%_at_80%_0%,rgba(63,136,57,0.18),transparent_60%)]"
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-7xl">
        <div className="grid gap-12 lg:grid-cols-12 lg:gap-16">
          <div className="min-w-0 lg:col-span-5">
            <p className="reveal inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-sm font-medium text-agro-sprout">
              {L("home.problem.eyebrow")}
            </p>
            <h2 className="display-heading reveal mt-6 font-display text-3xl font-semibold leading-[1.12] tracking-tight sm:text-4xl lg:text-[2.75rem]">
              {L("home.problem.title")}
            </h2>
            <p className="reveal mt-5 max-w-lg text-base leading-relaxed text-agro-sprout/85 sm:text-lg">
              {L("home.problem.subtitle")}
            </p>
            <div className="reveal mt-8 border-l border-agro-leaf/50 pl-4 sm:pl-5">
              <p className="max-w-md text-sm leading-relaxed text-agro-sprout/75 sm:text-[0.95rem]">
                {L("home.problem.kicker")}
              </p>
            </div>
          </div>

          <div className="min-w-0 lg:col-span-7">
            <ul className="divide-y divide-white/10 rounded-3xl border border-white/10 bg-white/[0.03]">
              {problems.map((item, index) => (
                <li
                  key={index}
                  className="reveal group p-6 transition-colors duration-200 hover:bg-white/[0.04] sm:p-8"
                >
                  <div className="flex gap-5 sm:gap-7">
                    <span
                      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-agro-sprout/30 bg-agro-canopy/30 font-mono text-xs font-semibold tracking-wider text-agro-sprout"
                      aria-hidden="true"
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0">
                      <h3 className="font-display text-xl font-semibold tracking-tight text-white sm:text-2xl">
                        {item.title}
                      </h3>
                      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-agro-sprout/80 sm:text-base">
                        {item.description}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
