/**
 * Browser-side calls to the same-origin auth API (`/api/v1/auth/*`, proxied to the jobs service).
 * The session JWT lives in an httpOnly cookie: it is never read by JS or put in web storage.
 */

const AUTH_API = "/api/v1/auth";
/** Next.js route that expires the session cookie when the API cannot (see `logout`). */
const CLEAR_SESSION_ROUTE = "/logout";

export const INVALID_CREDENTIALS_MESSAGE = "Invalid username or password.";
export const NETWORK_ERROR_MESSAGE =
  "Could not reach the server. Check your connection and try again.";
export const UNEXPECTED_ERROR_MESSAGE =
  "Something went wrong while signing in. Please try again.";

export type CurrentUser = {
  username: string;
  first_name: string;
  last_name: string;
  initials: string;
  email: string;
};

export type LoginResult = { ok: true } | { ok: false; message: string };

export function rateLimitMessage(retryAfterSeconds: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60));
  return `Too many attempts, try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`;
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${AUTH_API}/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    return { ok: false, message: NETWORK_ERROR_MESSAGE };
  }

  if (response.ok) {
    return { ok: true };
  }
  if (response.status === 401) {
    return { ok: false, message: INVALID_CREDENTIALS_MESSAGE };
  }
  if (response.status === 429) {
    const retryAfter = Number(response.headers.get("Retry-After"));
    return {
      ok: false,
      message: rateLimitMessage(Number.isFinite(retryAfter) ? retryAfter : 60),
    };
  }
  return { ok: false, message: UNEXPECTED_ERROR_MESSAGE };
}

/**
 * The signed-in user's identity, or `null` when the API rejects the session (401).
 * Throws on network or server errors so callers can show a fallback.
 */
export async function fetchCurrentUser(
  signal?: AbortSignal,
): Promise<CurrentUser | null> {
  const response = await fetch(`${AUTH_API}/me`, {
    credentials: "include",
    signal,
  });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`GET ${AUTH_API}/me failed with ${response.status}`);
  }
  return (await response.json()) as CurrentUser;
}

/**
 * End the session by expiring the `cn_session` cookie; callers then navigate to /login (see `useLogout`).
 * The API only clears the cookie for a valid session (401 otherwise) and may be unreachable,
 * so in those cases the Next.js clear-session route expires the cookie instead.
 */
export async function endSession(): Promise<void> {
  try {
    const response = await fetch(`${AUTH_API}/logout`, {
      method: "POST",
      credentials: "include",
    });
    if (response.ok) {
      return;
    }
  } catch {
    // Fall through to the frontend route.
  }

  try {
    await fetch(CLEAR_SESSION_ROUTE, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Nothing else to try; the proxy still rejects an invalid or expired cookie.
  }
}
