/**
 * Static UI build: access passes (JWTs) are disabled.
 *
 * The exported surface is kept so pages and layouts that read a pass continue
 * to type-check and render their neutral "no valid pass" state instead of
 * redirecting or erroring.
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
  jti: string;
  kind: "verify" | "reset";
  email: string;
  account_id: string | null;
  stage: "pending" | "code_verified";
  wrong_total: number;
  consumed_at: string | null;
  dead_at: string | null;
  expires_at: string;
};

export type SessionRow = {
  id: string;
  account_id: string;
  expires_at: string;
  revoked_at: string | null;
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
  input: { accountId?: string; email: string },
): Promise<{ token: string; jti: string; expiresAt: Date }> {
  return {
    token: "",
    jti: `static-${kind}`,
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
  _kind: PassKind,
): Promise<VerifiedPass | null> {
  return null;
}

export async function setPassCookie(): Promise<void> {
  return;
}

export async function clearPassCookies(): Promise<void> {
  return;
}
