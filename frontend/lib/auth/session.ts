import { jwtVerify } from "jose";

/** httpOnly cookie set by the jobs service on login; never readable from browser JS. */
export const SESSION_COOKIE_NAME = "cn_session";

const JWT_ALGORITHM = "HS256";

/**
 * Check the session JWT's HS256 signature and expiry against the shared secret.
 * Returns false (never throws) for a missing secret or any invalid token.
 */
export async function isValidSessionToken(
  token: string | undefined,
  secret: string | undefined,
): Promise<boolean> {
  if (!token || !secret) {
    return false;
  }
  try {
    await jwtVerify(token, new TextEncoder().encode(secret), {
      algorithms: [JWT_ALGORITHM],
      requiredClaims: ["sub", "iat", "exp"],
    });
    return true;
  } catch {
    return false;
  }
}
