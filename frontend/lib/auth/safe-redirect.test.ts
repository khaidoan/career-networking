import { describe, expect, it } from "vitest";

import { getSafeRedirectPath } from "./safe-redirect";

describe("getSafeRedirectPath", () => {
  it("keeps relative in-app paths and rejects anything that could leave the app", () => {
    expect(getSafeRedirectPath("/companies?page=2")).toBe("/companies?page=2");

    for (const unsafe of [
      null,
      "",
      "companies",
      "//evil.com",
      "/\\evil.com",
      "https://evil.com",
      "javascript:alert(1)",
      "/\t/evil.com",
    ]) {
      expect(getSafeRedirectPath(unsafe)).toBe("/inbox/recommended");
    }
  });
});
