import { NextResponse, type NextRequest } from "next/server";

import {
  DEFAULT_AUTHENTICATED_PATH,
  LOGIN_PATH,
  getSafeRedirectPath,
} from "@/lib/auth/safe-redirect";
import { SESSION_COOKIE_NAME, isValidSessionToken } from "@/lib/auth/session";

/**
 * Route protection (Next.js 16 "proxy", formerly middleware).
 * Every page needs a valid `cn_session` JWT except the login page, the health probe,
 * the cookie-clearing logout route and static assets (excluded by the matcher below).
 */
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const authenticated = await isValidSessionToken(
    token,
    process.env.CAREER_NETWORKING_JWT_SECRET,
  );

  if (pathname === LOGIN_PATH) {
    if (!authenticated) {
      return NextResponse.next();
    }
    const next = request.nextUrl.searchParams.get("next");
    return redirectTo(request, getSafeRedirectPath(next));
  }

  if (!authenticated) {
    const loginUrl = new URL(LOGIN_PATH, request.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("next", `${pathname}${search}`);
    }
    const response = NextResponse.redirect(loginUrl);
    if (token) {
      // Drop an expired or tampered cookie so the browser stops sending it.
      response.cookies.set(SESSION_COOKIE_NAME, "", { path: "/", maxAge: 0 });
    }
    return response;
  }

  if (pathname === "/") {
    return redirectTo(request, DEFAULT_AUTHENTICATED_PATH);
  }
  return NextResponse.next();
}

function redirectTo(request: NextRequest, path: string) {
  return NextResponse.redirect(new URL(path, request.url));
}

export const config = {
  matcher: [
    /*
     * Everything except: /health, /logout, Next.js internals (/_next/*), favicon,
     * robots/sitemap, font files and other static assets by extension.
     */
    "/((?!health$|logout$|_next/|favicon\\.ico$|robots\\.txt$|sitemap\\.xml$|fonts/|.*\\.(?:svg|png|jpe?g|gif|webp|avif|ico|woff2?|ttf|otf|eot|css|js|map|txt|webmanifest)$).*)",
  ],
};
