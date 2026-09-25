export const DEFAULT_AUTHENTICATED_PATH = "/inbox/recommended";
export const LOGIN_PATH = "/login";

// Placeholder origin used only to parse relative paths; never appears in a redirect.
const PARSE_ORIGIN = "http://in-app.invalid";

/**
 * Resolve a post-login `next` value to a relative in-app path.
 * Anything that could leave the app (absolute URLs, protocol-relative `//host`,
 * backslash tricks, control characters) falls back to the default inbox.
 */
export function getSafeRedirectPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return DEFAULT_AUTHENTICATED_PATH;
  }
  // Browsers treat "\" as "/" and strip tabs/newlines, so "/\evil.com" would become "//evil.com".
  if (next.includes("\\") || /[\u0000-\u001f\u007f]/.test(next)) {
    return DEFAULT_AUTHENTICATED_PATH;
  }

  let url: URL;
  try {
    url = new URL(next, PARSE_ORIGIN);
  } catch {
    return DEFAULT_AUTHENTICATED_PATH;
  }
  if (url.origin !== PARSE_ORIGIN || url.pathname === LOGIN_PATH) {
    return DEFAULT_AUTHENTICATED_PATH;
  }
  return `${url.pathname}${url.search}${url.hash}`;
}
