import { describe, expect, it } from "vitest";

import { timeZoneOptions } from "./timezones";

describe("timeZoneOptions", () => {
  it("lists UTC and the browser's zones with readable labels, plus extra names", () => {
    const options = timeZoneOptions(["Asia/Calcutta", ""]);
    const values = options.map((option) => option.value);

    expect(values).toContain("UTC");
    expect(values).toContain("Asia/Calcutta");
    expect(values).not.toContain("");
    expect(new Set(values).size).toBe(values.length);
    expect(
      options.find((option) => option.value === "America/Los_Angeles")?.label,
    ).toBe("America/Los Angeles");
  });
});
