import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function TargetUsers({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);

  const users = [
    {
      title: t("home.users.title1").text,
      description: t("home.users.desc1").text,
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
        </svg>
      ),
    },
    {
      title: t("home.users.title2").text,
      description: t("home.users.desc2").text,
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
        </svg>
      ),
    },
    {
      title: t("home.users.title3").text,
      description: t("home.users.desc3").text,
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
      ),
    },
  ];

  return (
    <section className="w-full border-t border-agro-clay/60 bg-agro-stone/20 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-5 md:grid-cols-3">
          {users.map((user, index) => (
            <div
              key={user.title}
              className="reveal group flex h-full flex-col rounded-3xl border border-agro-clay/80 bg-white p-6 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-7"
            >
              <div className="flex items-start justify-between gap-4">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-agro-mint text-agro-canopy ring-1 ring-agro-sprout/70 transition-colors duration-200 group-hover:bg-agro-canopy group-hover:text-white group-hover:ring-agro-canopy">
                  {user.icon}
                </span>
                <span
                  className="font-mono text-xs font-semibold tracking-[0.18em] text-agro-canopy/45"
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="mt-5 font-display text-xl font-semibold tracking-tight text-agro-ink">
                {user.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-agro-slate sm:text-base">
                {user.description}
              </p>
            </div>
          ))}
        </div>

        <p className="reveal mx-auto mt-10 flex max-w-3xl items-center justify-center gap-4 text-center text-sm font-medium tracking-wide text-agro-canopy sm:text-base">
          <span className="hidden h-px flex-1 bg-agro-clay/80 sm:inline-block" aria-hidden="true" />
          <span>{t("home.users.tagline").text}</span>
          <span className="hidden h-px flex-1 bg-agro-clay/80 sm:inline-block" aria-hidden="true" />
        </p>
      </div>
    </section>
  );
}
