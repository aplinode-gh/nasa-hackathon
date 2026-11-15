import "server-only";

import { backendFetch } from "@/lib/backend";

/**
 * Server-side pass helpers backed by FastAPI auth cookies.
 * verify/reset pass validity is resolved via backend `/api/auth/pass/:kind`.
 */

export type PassKind = "verify" | "reset" | "session";

export const PASS_COOKIE_NAMES: Record<PassKind, string> = {
  verify: "agro_verify",
  reset: "agro_reset",
  session: "agro_session",
};

export const PASS_TTL_SECONDS: Record<PassKind, number> = {
  verify: 60 * 60,
  reset: 60 * 60,
  session: 7 * 24 * 60 * 60,
};

export type PassClaims = {
  sub: string;
  email: string;
  typ: PassKind;
  jti: string;
};

export type PassStateRow = {
  jti?: string;
  kind?: "verify" | "reset";
  email: string | null;
  account_id: string | null;
  stage: "pending" | "code_verified" | null;
  wrong_total?: number;
  consumed_at?: string | null;
  dead_at?: string | null;
  expires_at?: string | null;
};

export type SessionRow = {
  id: string;
  account_id: string;
  expires_at?: string | null;
  revoked_at?: string | null;
};

export type VerifiedPass =
  | { kind: "verify"; claims: PassClaims; row: PassStateRow }
  | { kind: "reset"; claims: PassClaims; row: PassStateRow }
  | { kind: "session"; claims: PassClaims; row: SessionRow };

export async function decodePassToken(
  _token: string,
  _kind: PassKind,
): Promise<PassClaims | null> {
  return null;
}

export async function signPassToken(
  _claims: PassClaims,
  _ttlSeconds: number,
): Promise<string> {
  return "";
}

export async function mintPass(
  kind: PassKind,
  _input: { accountId?: string; email: string },
): Promise<{ token: string; jti: string; expiresAt: Date }> {
  return {
    token: "",
    jti: `backend-${kind}`,
    expiresAt: new Date(Date.now() + PASS_TTL_SECONDS[kind] * 1000),
  };
}

export async function readValidPass(
  kind: "verify",
): Promise<Extract<VerifiedPass, { kind: "verify" }> | null>;
export async function readValidPass(
  kind: "reset",
): Promise<Extract<VerifiedPass, { kind: "reset" }> | null>;
export async function readValidPass(
  kind: "verify" | "reset",
): Promise<Extract<VerifiedPass, { kind: "verify" | "reset" }> | null>;
export async function readValidPass(
  kind: "session",
): Promise<Extract<VerifiedPass, { kind: "session" }> | null>;
export async function readValidPass(
  kind: PassKind,
): Promise<VerifiedPass | null> {
  try {
    if (kind === "session") {
      const res = await backendFetch("/api/auth/session");
      if (!res.ok) return null;
      const data = (await res.json()) as { session?: { accountId?: string; email?: string } };
      if (!data?.session?.accountId || !data?.session?.email) return null;
      return {
        kind: "session",
        claims: {
          sub: String(data.session.accountId),
          email: String(data.session.email),
          typ: "session",
          jti: "",
        },
        row: {
          id: "",
          account_id: String(data.session.accountId),
        },
      };
    }

    const res = await backendFetch(`/api/auth/pass/${kind}`);
    if (!res.ok) return null;
    const data = (await res.json()) as {
      valid?: boolean;
      claims?: { sub?: string | null; email?: string | null; typ?: string; jti?: string | null };
      row?: { stage?: "pending" | "code_verified" | null; account_id?: string | null; email?: string | null };
    };
    if (!data?.valid || !data.claims?.email) return null;

    const claims: PassClaims = {
      sub: String(data.claims.sub ?? ""),
      email: String(data.claims.email),
      typ: kind,
      jti: String(data.claims.jti ?? ""),
    };
    const row: PassStateRow = {
      kind,
      email: data.row?.email ?? data.claims.email ?? null,
      account_id: data.row?.account_id ?? null,
      stage: data.row?.stage ?? null,
    };
    return { kind, claims, row } as VerifiedPass;
  } catch {
    return null;
  }
}

export async function setPassCookie(): Promise<void> {
  return;
}

export async function clearPassCookies(): Promise<void> {
  return;
}
