import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

export default async function FeatureMatrix({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const tiers = [
    {
      index: "01",
      name: L("home.matrix.tier1Name"),
      badge: L("home.matrix.tier1Badge"),
      shell: "border border-agro-clay/80 bg-white",
      head: "border-b border-agro-clay/70 bg-agro-stone/40",
      badgeClass: "border border-agro-clay bg-white text-agro-slate",
      item: "border border-agro-clay/70 bg-white hover:border-agro-sprout hover:bg-agro-mint/20",
      num: "text-agro-canopy/50",
      title: "text-agro-ink",
      desc: "text-agro-slate",
      count: "text-agro-slate/70",
      features: [
        { title: L("home.matrix.t1f1Title"), description: L("home.matrix.t1f1Body") },
        { title: L("home.matrix.t1f2Title"), description: L("home.matrix.t1f2Body") },
        { title: L("home.matrix.t1f3Title"), description: L("home.matrix.t1f3Body") },
        { title: L("home.matrix.t1f4Title"), description: L("home.matrix.t1f4Body") },
      ],
    },
    {
      index: "02",
      name: L("home.matrix.tier2Name"),
      badge: L("home.matrix.tier2Badge"),
      shell: "border border-agro-sprout/80 bg-white shadow-sm ring-1 ring-agro-sprout/30",
      head: "border-b border-agro-sprout/60 bg-agro-mint/50",
      badgeClass: "border border-agro-canopy/20 bg-agro-canopy text-white",
      item: "border border-agro-sprout/60 bg-white hover:border-agro-canopy/40 hover:bg-agro-mint/30",
      num: "text-agro-canopy/60",
      title: "text-agro-ink",
      desc: "text-agro-slate",
      count: "text-agro-canopy/70",
      features: [
        { title: L("home.matrix.t2f1Title"), description: L("home.matrix.t2f1Body") },
        { title: L("home.matrix.t2f2Title"), description: L("home.matrix.t2f2Body") },
        { title: L("home.matrix.t2f3Title"), description: L("home.matrix.t2f3Body") },
        { title: L("home.matrix.t2f4Title"), description: L("home.matrix.t2f4Body") },
        { title: L("home.matrix.t2f5Title"), description: L("home.matrix.t2f5Body") },
      ],
    },
    {
      index: "03",
      name: L("home.matrix.tier3Name"),
      badge: L("home.matrix.tier3Badge"),
      shell: "border border-agro-forest/80 bg-agro-forest text-white shadow-lg",
      head: "border-b border-white/10 bg-white/[0.04]",
      badgeClass: "border border-agro-sprout/30 bg-white/10 text-agro-sprout",
      item: "border border-white/10 bg-white/[0.03] hover:border-agro-sprout/30 hover:bg-white/[0.06]",
      num: "text-agro-sprout/60",
      title: "text-white",
      desc: "text-agro-sprout/80",
      count: "text-agro-sprout/60",
      features: [
        { title: L("home.matrix.t3f1Title"), description: L("home.matrix.t3f1Body") },
        { title: L("home.matrix.t3f2Title"), description: L("home.matrix.t3f2Body") },
        { title: L("home.matrix.t3f3Title"), description: L("home.matrix.t3f3Body") },
        { title: L("home.matrix.t3f4Title"), description: L("home.matrix.t3f4Body") },
        { title: L("home.matrix.t3f5Title"), description: L("home.matrix.t3f5Body") },
      ],
    },
  ];

  return (
    <section
      id="matrix"
      className="w-full border-t border-agro-clay/60 bg-white px-4 py-20 sm:px-6 lg:px-8 lg:py-28"
    >
      <div className="mx-auto max-w-7xl">
        <div className="max-w-2xl">
          <p className="reveal inline-flex items-center gap-2 rounded-full border border-agro-sprout/70 bg-agro-mint/50 px-3 py-1 text-sm font-medium text-agro-canopy">
            {L("home.matrix.eyebrow")}
          </p>
          <h2 className="display-heading reveal mt-6 font-display text-3xl font-semibold leading-[1.12] tracking-tight text-agro-ink sm:text-4xl lg:text-[2.75rem]">
            {L("home.matrix.title")}
          </h2>
          <p className="reveal mt-5 text-base leading-relaxed text-agro-slate sm:text-lg">
            {L("home.matrix.subtitle")}
          </p>
        </div>

        <div className="mt-14 space-y-6">
          {tiers.map((tier) => (
            <article key={tier.index} className={`reveal overflow-hidden rounded-3xl ${tier.shell}`}>
              <div className={`flex flex-wrap items-center gap-x-4 gap-y-3 px-6 py-5 sm:px-8 ${tier.head}`}>
                <div className="flex min-w-0 items-center gap-3">
                  <span className="font-mono text-xs font-semibold tracking-[0.18em] opacity-70">{tier.index}</span>
                  <h3 className="font-display text-xl font-semibold tracking-tight sm:text-2xl">{tier.name}</h3>
                </div>
                <div className="ms-auto flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${tier.badgeClass}`}>
                    {tier.badge}
                  </span>
                  <span className={`text-xs font-medium ${tier.count}`}>
                    {String(tier.features.length).padStart(2, "0")} {t("home.matrix.capabilitiesLabel").text}
                  </span>
                </div>
              </div>

              <ul className="grid gap-4 p-6 sm:grid-cols-2 sm:p-8 lg:gap-x-6">
                {tier.features.map((feature, i) => (
                  <li
                    key={i}
                    className={`group rounded-2xl p-5 transition-colors duration-200 ${tier.item}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className={`mt-0.5 font-mono text-xs font-semibold tracking-wider ${tier.num}`} aria-hidden="true">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <h4 className={`font-semibold tracking-tight ${tier.title}`}>{feature.title}</h4>
                        <p className={`mt-2 text-sm leading-relaxed ${tier.desc}`}>{feature.description}</p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
