"use client";

import { useState } from "react";

export interface CtaFormStrings {
  emailLabel: string;
  submit: string;
  success: string;
}

export default function CtaForm({ strings }: { strings: CtaFormStrings }) {
  const [submitted, setSubmitted] = useState(false);

  if (submitted) {
    return (
      <div
        className="mx-auto mt-8 flex max-w-xl items-center justify-center gap-3 rounded-2xl border border-agro-sprout/35 bg-white/10 px-5 py-4 text-left shadow-sm sm:px-6"
        role="status"
      >
        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-agro-sprout text-agro-forest" aria-hidden="true">
          <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </span>
        <p className="text-sm leading-relaxed text-white sm:text-[0.95rem]">
          {strings.success}
        </p>
      </div>
    );
  }

  return (
    <form
      className="mx-auto mt-8 flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:items-center"
      onSubmit={(e) => {
        e.preventDefault();
        setSubmitted(true);
      }}
    >
      <label htmlFor="cta-email" className="sr-only">
        {strings.emailLabel}
      </label>
      <input
        id="cta-email"
        name="email"
        type="email"
        required
        autoComplete="email"
        inputMode="email"
        placeholder="you@example.com"
        dir="ltr"
        className="h-12 w-full min-w-0 flex-1 rounded-xl border border-white/20 bg-white/95 px-4 text-base font-medium text-agro-ink shadow-sm placeholder:font-normal placeholder:text-agro-cloud/90 transition-colors duration-200 focus:border-agro-sprout focus:outline-none focus:ring-2 focus:ring-agro-sprout/30 sm:h-[3.25rem]"
      />
      <button
        type="submit"
        className="inline-flex h-12 w-full cursor-pointer items-center justify-center rounded-xl bg-white px-7 text-sm font-semibold text-agro-forest shadow-sm transition-colors duration-200 hover:bg-agro-mint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white sm:h-[3.25rem] sm:w-auto sm:min-w-[11.5rem]"
      >
        {strings.submit}
      </button>
    </form>
  );
}
