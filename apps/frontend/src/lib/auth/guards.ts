/**
 * Static UI build: authentication is disabled.
 *
 * Protected screens render with a demo session so the interface is fully
 * browsable without a backend. Public pages are treated as signed-out.
 */

export type SessionContext = {
  accountId: string;
  email: string;
};

const DEMO_SESSION: SessionContext = {
  accountId: "demo-account",
  email: "farmer@demo.agropioo.app",
};

/** Protected pages always resolve to the demo session. */
export async function requireSessionPage(): Promise<SessionContext> {
  return DEMO_SESSION;
}

/** Guest-only pages never redirect in the static build. */
export async function requireGuestPage(): Promise<void> {
  return;
}

/** Protected data APIs are not present; the demo session is returned. */
export async function requireSessionApi(): Promise<SessionContext> {
  return DEMO_SESSION;
}

/** Public pages always render as signed-out. */
export async function getSessionOptional(): Promise<SessionContext | null> {
  return null;
}
