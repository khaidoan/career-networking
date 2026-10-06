import { describe, expect, it } from "vitest";

import { formatDaysAgo, matchStrength } from "./format";

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

describe("formatDaysAgo", () => {
  const now = new Date(2026, 9, 6, 9);

  it.each([
    [new Date(2026, 9, 6, 1), "today"],
    [new Date(2026, 9, 5, 23), "1 day ago"],
    [new Date(2026, 9, 4, 12), "2 days ago"],
    [new Date(2026, 8, 6, 12), "30 days ago"],
    [new Date(2026, 9, 7, 12), "today"],
  ])("formats %s as %s", (date, expected) => {
    expect(formatDaysAgo(date.toISOString(), now)).toBe(expected);
  });

  it("returns null for a missing or invalid date", () => {
    expect(formatDaysAgo(null, now)).toBeNull();
    expect(formatDaysAgo("not a date", now)).toBeNull();
  });
});
