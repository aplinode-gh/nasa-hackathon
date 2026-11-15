import "server-only";

import { cookies } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

function resolveBackendUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${BACKEND_URL}${normalized}`;
}

/**
 * Server-side fetch against the FastAPI backend.
 *
 * Forwards the browser cookie header so authenticated endpoints work from
 * React Server Components. The frontend also proxies `/api/*` to the backend
 * for client-side fetches via Next.js rewrites.
 */
export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  try {
    const response = await fetch(resolveBackendUrl(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}
