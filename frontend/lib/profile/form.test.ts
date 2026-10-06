import { describe, expect, it } from "vitest";

import { applyResumeDefaults, toFormValues } from "./form";
import type { Preferences } from "@/lib/api/preferences";

const EMPTY: Preferences = {
  desired_titles: [],
  excluded_title_words: [],
  hard_skills: [],
  soft_skills: [],
  country: null,
  currency: null,
  salary_min: null,
  salary_max: null,
  seniority: [],
  address: null,
  gender: null,
  eeo_answers: {},
  additional_information: null,
  auto_apply: false,
  fetch_time: null,
  fetch_timezone: null,
  resume: null,
  job_fetching: {
    enabled: false,
    missing: ["desired_titles", "country", "fetch_time", "fetch_timezone"],
    next_run_at: null,
  },
};

const FROM_RESUME = {
  seniority: ["senior"],
  country: "GB",
  currency: "GBP",
  address: "1 King Street, London",
};

describe("applyResumeDefaults", () => {
  it("fills empty fields and replaces a browser guess and its currency", () => {
    const empty = toFormValues(EMPTY);
    expect(applyResumeDefaults(empty, FROM_RESUME)).toMatchObject({
      seniority: ["senior"],
      country: "GB",
      currency: "GBP",
      address: "1 King Street, London",
    });

    const guessed = { ...empty, country: "CA", currency: "CAD" };
    expect(applyResumeDefaults(guessed, FROM_RESUME, "CA")).toMatchObject({
      country: "GB",
      currency: "GBP",
    });
  });

  it("keeps values the user chose", () => {
    const chosen = {
      ...toFormValues(EMPTY),
      seniority: ["mid"],
      country: "CA",
      currency: "USD",
      address: "9 Queen Street, Toronto",
    };
    expect(applyResumeDefaults(chosen, FROM_RESUME)).toMatchObject({
      seniority: ["mid"],
      country: "CA",
      currency: "USD",
      address: "9 Queen Street, Toronto",
    });
    // A currency picked by hand survives replacing the guessed country.
    expect(
      applyResumeDefaults({ ...chosen, seniority: [] }, FROM_RESUME, "CA"),
    ).toMatchObject({ seniority: ["senior"], country: "GB", currency: "USD" });
  });
});
