import { NextResponse, type NextRequest } from "next/server";

import { isLocale } from "@/lib/i18n/config";

/**
 * Hybrid locale routing for the marketing site.
 *  - "/ur/features"  → real route under app/(site)/[locale], untouched.
 *  - "/features"     → internally rewritten to /en/features.
 *  - Farmer-app and auth routes are real routes outside [locale], untouched.
 */
export function proxy(request: NextRequest) {
  const firstSegment = request.nextUrl.pathname.split("/")[1] ?? "";

  if (isLocale(firstSegment)) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = `/en${request.nextUrl.pathname === "/" ? "" : request.nextUrl.pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\..*|dashboard|farms|advisor|prices|notifications|settings|more|records|forgot-password|reset-password|verify|weather|onboarding|crops).*)",
  ],
};
