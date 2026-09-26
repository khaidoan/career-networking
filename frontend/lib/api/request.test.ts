import { describe, expect, it, vi } from "vitest";

import {
  INVALID_INPUT_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  requestJson,
  SESSION_EXPIRED_MESSAGE,
} from "./request";

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("requestJson", () => {
  it("maps a 401 to the session-expired failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ detail: "Not authenticated" }, 401)),
    );

    expect(await requestJson("/api/v1/jobs/1")).toEqual({
      ok: false,
      kind: "sessionExpired",
      message: SESSION_EXPIRED_MESSAGE,
      fieldErrors: {},
    });
  });

  it("maps a network failure to the network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    expect(await requestJson("/api/v1/jobs/1")).toMatchObject({
      ok: false,
      kind: "network",
      message: NETWORK_ERROR_MESSAGE,
    });
  });

  it("maps 422 details to per-field messages and sends the session cookie", async () => {
    const fetchMock = vi.fn(async () =>
      json(
        {
          detail: [
            {
              type: "value_error",
              loc: ["body", "linkedin_url"],
              msg: "Value error, must be a linkedin.com URL",
            },
          ],
        },
        422,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await requestJson("/api/v1/companies", { method: "POST" });

    expect(result).toEqual({
      ok: false,
      kind: "invalid",
      message: INVALID_INPUT_MESSAGE,
      fieldErrors: { linkedin_url: "Must be a linkedin.com URL" },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/companies",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
