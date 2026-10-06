import { describe, expect, it } from "vitest";

import { matchStrength } from "./format";

describe("matchStrength", () => {
  it.each([
    [100, "Excellent"],
    [95, "Excellent"],
    [94, "Strong"],
    [80, "Strong"],
    [79, "Good"],
    [60, "Good"],
    [59, "Weak"],
    [0, "Weak"],
  ])("classifies a score of %i as %s", (score, strength) => {
    expect(matchStrength(score)).toBe(strength);
  });
});
