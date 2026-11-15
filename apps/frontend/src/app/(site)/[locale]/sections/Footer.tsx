import Image from "next/image";
import logo from "@/references/AgroAI-logo-footer.png";
import { getDictionary } from "@/lib/i18n/server";
import type { Locale } from "@/lib/i18n/config";

function FacebookIcon() {
  return (
    <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <rect x="2" y="2" width="20" height="20" rx="5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.5 6.5h.01" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function LinkedinIcon() {
  return (
    <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4V9h4v1.5A6 6 0 0116 8z" />
      <rect x="2" y="9" width="4" height="12" rx="0.5" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

function YoutubeIcon() {
  return (
    <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path d="M22.54 6.42a2.78 2.78 0 00-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 00-1.94 2A29 29 0 001 11.75a29 29 0 00.46 5.33A2.78 2.78 0 003.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 001.94-2 29 29 0 00.46-5.25 29 29 0 00-.46-5.33z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 15.02l5.75-3.27-5.75-3.27z" />
    </svg>
  );
}

const socials = [
  { label: "Facebook", href: "#", Icon: FacebookIcon },
  { label: "Instagram", href: "#", Icon: InstagramIcon },
  { label: "X (Twitter)", href: "#", Icon: XIcon },
  { label: "LinkedIn", href: "#", Icon: LinkedinIcon },
  { label: "YouTube", href: "#", Icon: YoutubeIcon },
];

export default async function Footer({ hrefPrefix = "", locale }: { hrefPrefix?: string; locale: Locale }) {
  const { t } = await getDictionary(locale);
  const sectionHref = (anchor: string) => `${hrefPrefix}${anchor}`;

  const pageLinks = [
    { label: t("nav.whyAgroAI").text, href: "/why-agroai" },
    { label: t("nav.features").text, href: "/features" },
    { label: t("nav.howItWorks").text, href: "/how-it-works" },
    { label: t("nav.vision").text, href: "/vision" },
    { label: t("nav.getEarlyAccess").text, href: "#get-started" },
  ];

  const legalLinks = [
    { label: t("home.footer.privacy").text, href: "#" },
    { label: t("home.footer.terms").text, href: "#" },
    { label: t("home.footer.cookies").text, href: "#" },
    { label: t("home.footer.disclaimer").text, href: "#" },
  ];

  return (
    <footer className="w-full border-t border-white/10 bg-agro-night px-4 pb-8 pt-14 text-white sm:px-6 lg:px-8 lg:pt-16">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-10 border-b border-white/10 pb-10 md:grid-cols-2 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-5">
            <a href={hrefPrefix ? "/" : "#top"} className="inline-flex items-center rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-agro-sprout">
              <Image src={logo} alt="AgroAI" className="h-14 w-auto sm:h-16" />
            </a>
            <p className="mt-5 max-w-md text-sm leading-relaxed text-white/70 sm:text-base">
              {t("home.footer.tagline").text}
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-2.5">
              {socials.map(({ label, href, Icon }) => (
                <a
                  key={label}
                  href={href}
                  aria-label={label}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/12 bg-white/[0.04] text-white/80 transition-colors duration-200 hover:border-agro-canopy/60 hover:bg-agro-canopy hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-sprout"
                >
                  <Icon />
                </a>
              ))}
            </div>
          </div>

          <nav className="lg:col-span-2" aria-label={t("home.footer.pagesNavLabel").text}>
            <h3 className="text-sm font-semibold tracking-wide text-agro-sprout">{t("home.footer.pagesHeading").text}</h3>
            <ul className="mt-4 space-y-3">
              {pageLinks.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href.startsWith("#") ? sectionHref(link.href) : link.href}
                    className="text-sm text-white/70 transition-colors duration-200 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-sprout"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav className="lg:col-span-2" aria-label={t("home.footer.legalNavLabel").text}>
            <h3 className="text-sm font-semibold tracking-wide text-agro-sprout">{t("home.footer.legalHeading").text}</h3>
            <ul className="mt-4 space-y-3">
              {legalLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-white/70 transition-colors duration-200 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-sprout"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="lg:col-span-3">
            <h3 className="text-sm font-semibold tracking-wide text-agro-sprout">{t("home.footer.contactHeading").text}</h3>
            <ul className="mt-4 space-y-3 text-sm text-white/70">
              <li>
                <a
                  href="mailto:hello@agroai.com"
                  className="transition-colors duration-200 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-agro-sprout"
                >
                  hello@agroai.com
                </a>
              </li>
              <li>{t("home.footer.country").text}</li>
              <li>{t("common.builtForPakistan").text}</li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col items-start justify-between gap-4 pt-8 sm:flex-row sm:items-center">
          <p className="text-sm text-white/55">
            {t("home.footer.copyright", { year: String(new Date().getFullYear()) }).text}
          </p>
          <p className="text-xs font-medium tracking-[0.12em] text-white/45 uppercase">
            {t("home.footer.motto").text}
          </p>
        </div>
      </div>
    </footer>
  );
}
