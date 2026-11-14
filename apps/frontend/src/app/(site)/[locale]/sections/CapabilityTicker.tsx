import { localized } from "@/lib/i18n/localized";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

function TickerContent({ items }: { items: React.ReactNode[] }) {
  return (
    <div className="flex shrink-0 items-center">
      {items.map((item, index) => (
        <span
          key={index}
          className="flex items-center gap-4 pr-6 text-sm font-medium text-white/90 sm:gap-6 sm:pr-8 sm:text-[0.95rem]"
        >
          {item}
          <span className="inline-block h-1 w-1 shrink-0 rounded-full bg-agro-leaf" aria-hidden="true" />
        </span>
      ))}
    </div>
  );
}

export default async function CapabilityTicker({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);
  const L = (key: Parameters<typeof t>[0]) => localized(t(key), locale);

  const capabilities = [
    L("home.ticker.mandiPrices"),
    L("home.ticker.weatherAdvisories"),
    L("home.ticker.farmRecords"),
    L("home.ticker.advisoryLanguages"),
    L("home.ticker.offlineSms"),
  ];

  return (
    <div
      className="relative w-full overflow-hidden border-y border-agro-canopy/30 bg-agro-forest py-4 sm:py-4.5"
      aria-label={t("home.ticker.ariaLabel").text}
    >
      <div className="marquee-track flex w-max will-change-transform">
        <TickerContent items={capabilities} />
        <TickerContent items={capabilities} />
        <TickerContent items={capabilities} />
        <TickerContent items={capabilities} />
      </div>

      <div className="pointer-events-none absolute inset-y-0 start-0 w-16 bg-gradient-to-r from-agro-forest to-transparent rtl:bg-gradient-to-l sm:w-28" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-y-0 end-0 w-16 bg-gradient-to-l from-agro-forest to-transparent rtl:bg-gradient-to-r sm:w-28" aria-hidden="true" />
    </div>
  );
}
