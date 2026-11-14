import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function Solution({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const values = [
    {
      question: L("home.solution.card1Title"),
      description: L("home.solution.card1Body"),
      answer: L("home.solution.card1Answer"),
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.042 21.672L13.684 16.6m0 0l-2.51 2.225.569-9.47 5.227 7.917-3.286-.672zm-7.518-.267A8.25 8.25 0 1120.25 10.5M8.288 14.212A5.25 5.25 0 1117.25 10.5" />
        </svg>
      ),
    },
    {
      question: L("home.solution.card2Title"),
      description: L("home.solution.card2Body"),
      answer: L("home.solution.card2Answer"),
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      question: L("home.solution.card3Title"),
      description: L("home.solution.card3Body"),
      answer: L("home.solution.card3Answer"),
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
        </svg>
      ),
    },
  ];

  return (
    <section
      id="solution"
      className="w-full border-t border-agro-clay/60 bg-white px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-10 lg:grid-cols-12 lg:items-end lg:gap-12">
          <div className="min-w-0 lg:col-span-7">
            <p className="reveal inline-flex items-center gap-2 rounded-full border border-agro-sprout/70 bg-agro-mint/60 px-3 py-1 text-sm font-medium text-agro-canopy">
              {L("home.solution.eyebrow")}
            </p>
            <h2 className="display-heading reveal mt-6 max-w-3xl font-display text-3xl font-semibold leading-[1.12] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.75rem]">
              {L("home.solution.titleA")} {L("home.solution.titleB")}
            </h2>
          </div>
          <p className="reveal max-w-md text-base leading-relaxed text-agro-slate sm:text-lg lg:col-span-5">
            {L("home.solution.subtitle")}
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {values.map((item, index) => (
            <article
              key={index}
              className="reveal group flex h-full flex-col rounded-3xl border border-agro-clay/80 bg-white p-7 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-8"
            >
              <div className="flex items-start justify-between gap-4">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-agro-mint text-agro-canopy ring-1 ring-agro-sprout/70 transition-colors duration-200 group-hover:bg-agro-canopy group-hover:text-white group-hover:ring-agro-canopy">
                  {item.icon}
                </span>
                <span
                  className="font-mono text-xs font-semibold tracking-[0.18em] text-agro-canopy/50"
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>

              <h3 className="mt-6 font-display text-xl font-semibold tracking-tight text-agro-ink sm:text-2xl">
                {item.question}
              </h3>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-agro-slate sm:text-base">
                {item.description}
              </p>

              <div className="mt-7 border-t border-agro-clay/70 pt-5">
                <p className="flex items-start gap-3 text-sm leading-relaxed text-agro-forest">
                  <span
                    className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-agro-canopy/10 text-agro-canopy"
                    aria-hidden="true"
                  >
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 5l7 7-7 7" />
                    </svg>
                  </span>
                  <span className="font-medium">{item.answer}</span>
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
