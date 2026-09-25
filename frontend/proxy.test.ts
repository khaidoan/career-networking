// @vitest-environment node
import { SignJWT } from "jose";
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { proxy } from "./proxy";

const SECRET = "test-secret-with-at-least-32-characters!!";
const ORIGIN = "http://localhost:8080";

async function sessionToken({
  secret = SECRET,
  expiresIn = "1h",
}: { secret?: string; expiresIn?: string | number } = {}) {
  return new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject("admin")
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(new TextEncoder().encode(secret));
}

function requestFor(path: string, token?: string) {
  const headers = new Headers();
  if (token) {
    headers.set("cookie", `cn_session=${token}`);
  }
  return new NextRequest(new URL(path, ORIGIN), { headers });
}

function redirectLocation(response: Response) {
  const location = response.headers.get("location");
  return location ? new URL(location) : null;
}

beforeEach(() => {
  vi.stubEnv("CAREER_NETWORKING_JWT_SECRET", SECRET);
});

describe("proxy route protection", () => {
  it("redirects to /login with next when there is no valid session", async () => {
    const expired = await sessionToken({
      expiresIn: Math.floor(Date.now() / 1000) - 60,
    });
    const forged = await sessionToken({
      secret: "a-different-secret-that-is-also-long-enough",
    });

    for (const token of [undefined, "not-a-jwt", expired, forged]) {
      const response = await proxy(requestFor("/companies?page=2", token));
      const location = redirectLocation(response);

      expect(response.status).toBe(307);
      expect(location?.pathname).toBe("/login");
      expect(location?.searchParams.get("next")).toBe("/companies?page=2");
    }
  });

  it("sends an authenticated user from / and /login to the recommended inbox and lets protected pages through", async () => {
    const token = await sessionToken();

    for (const path of ["/", "/login"]) {
      const response = await proxy(requestFor(path, token));
      expect(response.status).toBe(307);
      expect(redirectLocation(response)?.pathname).toBe("/inbox/recommended");
    }

    const response = await proxy(requestFor("/prompts", token));
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});
