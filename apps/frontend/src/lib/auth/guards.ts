import "server-only";

import { redirect } from "next/navigation";
import { backendFetch } from "@/lib/backend";

export type SessionContext = {
  accountId: string;
  email: string;
  fullName?: string | null;
  emailVerified?: boolean;
};

type SessionResponse = {
  session?: SessionContext;
};

export async function getSessionOptional(): Promise<SessionContext | null> {
  const data = await backendFetch<SessionResponse>("/api/auth/session");
  return data?.session ?? null;
}

/** Protected pages require an authenticated backend session. */
export async function requireSessionPage(): Promise<SessionContext> {
  const session = await getSessionOptional();
  if (!session) {
    redirect("/login");
  }
  return session;
}

/** Guest-only pages redirect authenticated users to the dashboard. */
export async function requireGuestPage(): Promise<void> {
  const session = await getSessionOptional();
  if (session) {
    redirect("/dashboard");
  }
}

/** Protected server actions/APIs can require session context. */
export async function requireSessionApi(): Promise<SessionContext> {
  const session = await getSessionOptional();
  if (!session) {
    throw new Error("Unauthorized");
  }
  return session;
}
