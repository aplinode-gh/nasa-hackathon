import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";
import CtaForm, { type CtaFormStrings } from "./CtaForm";

export default async function CTA({ locale }: { locale: Locale }) {
  const { t } = await getDictionary(locale);

  const strings: CtaFormStrings = {
    emailLabel: t("home.cta.emailLabel").text,
    submit: t("nav.getEarlyAccess").text,
    success: t("home.cta.success").text,
  };

  return (
    <section
      id="get-started"
      className="relative w-full overflow-hidden bg-agro-forest px-4 py-20 text-white sm:px-6 lg:px-8 lg:py-28"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_45%_at_50%_0%,rgba(63,136,57,0.22),transparent_65%)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute -bottom-24 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-agro-canopy/20 blur-3xl" aria-hidden="true" />

      <div className="relative mx-auto max-w-3xl">
        <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] px-6 py-10 text-center shadow-[0_30px_80px_-40px_rgba(0,0,0,0.45)] backdrop-blur-sm sm:px-10 sm:py-14">
          <p className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-3 py-1 text-sm font-medium text-agro-sprout">
            {t("home.cta.eyebrow").text}
          </p>
          <h2 className="display-heading mx-auto mt-6 max-w-2xl font-display text-3xl font-semibold leading-[1.12] tracking-tight text-white sm:text-4xl lg:text-[2.75rem]">
            {t("home.cta.title").text}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-agro-sprout/85 sm:text-lg">
            {t("home.cta.subtitle").text}
          </p>

          <CtaForm strings={strings} />

          <p className="mt-5 text-sm text-agro-sprout/70">
            {t("home.cta.fineprint").text}
          </p>
        </div>
      </div>
    </section>
  );
}
