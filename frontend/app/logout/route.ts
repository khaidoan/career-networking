import { NextResponse } from "next/server";

import { SESSION_COOKIE_NAME } from "@/lib/auth/session";

/**
 * Expire the session cookie from the frontend origin.
 * Used by the logout action when the API cannot clear it (session already rejected or API down).
 * Public (excluded from the auth proxy) so it works with an invalid cookie.
 */
export function POST() {
  const response = new NextResponse(null, { status: 204 });
  response.cookies.set(SESSION_COOKIE_NAME, "", {
    path: "/",
    maxAge: 0,
    httpOnly: true,
    sameSite: "lax",
  });
  return response;
}
