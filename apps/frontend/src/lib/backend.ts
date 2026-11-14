import "server-only";

import { cookies } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Server-side fetch against the FastAPI backend.
 *
 * Forwards the browser cookie header so authenticated endpoints work from
 * React Server Components (the frontend proxies /api to the backend for
 * client fetches, but relative URLs do not resolve on the server).
 */
export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  try {
    const response = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: {
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
