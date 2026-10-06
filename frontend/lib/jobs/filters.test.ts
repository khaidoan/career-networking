import { describe, expect, it } from "vitest";

import { jobListQuery } from "@/lib/api/jobs";

import { activeFilterCount, jobFiltersFromParams } from "./filters";

describe("match strength filter", () => {
  it("keeps known match strengths from the URL and sends them to the API", () => {
    const filters = jobFiltersFromParams(
      new URLSearchParams("match=excellent&match=great&match=not_scored"),
    );

    expect(filters.match).toEqual(["excellent", "not_scored"]);
    expect(activeFilterCount(filters)).toBe(1);
    expect(jobListQuery("ignored", filters).getAll("match")).toEqual([
      "excellent",
      "not_scored",
    ]);
  });
});
