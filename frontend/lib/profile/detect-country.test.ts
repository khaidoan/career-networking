import { describe, expect, it } from "vitest";

import { detectCountry } from "./detect-country";

describe("detectCountry", () => {
  it("uses the time zone first, including legacy aliases", () => {
    expect(
      detectCountry({ timeZone: "Europe/Berlin", languages: ["en-US"] }),
    ).toBe("DE");
    expect(detectCountry({ timeZone: "Asia/Calcutta", languages: [] })).toBe(
      "IN",
    );
  });

  it("falls back to the first language with a region", () => {
    expect(
      detectCountry({ timeZone: "Etc/UTC", languages: ["fr", "en-GB"] }),
    ).toBe("GB");
  });

  it("returns undefined when nothing names a country", () => {
    expect(detectCountry({ timeZone: "UTC", languages: ["en"] })).toBe(
      undefined,
    );
    expect(detectCountry({ languages: ["not a locale"] })).toBe(undefined);
  });
});
