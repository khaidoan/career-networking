import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Preferences } from "@/lib/api/preferences";

import { RequireProfileSetup } from "./require-profile-setup";

const router = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));

const COMPLETE: Preferences = {
  desired_titles: ["Backend Engineer"],
  excluded_title_words: [],
  hard_skills: [],
  soft_skills: [],
  country: "US",
  currency: null,
  salary_min: null,
  salary_max: null,
  seniority: [],
  address: null,
  gender: null,
  eeo_answers: {},
  additional_information: null,
  auto_apply: false,
  fetch_time: "06:00",
  fetch_timezone: "UTC",
  job_fetching: { enabled: true, missing: [], next_run_at: null },
  resume: {
    file_type: "pdf",
    file_name: "cv.pdf",
    uploaded_at: "2026-09-25T10:00:00Z",
  },
};

function respondWith(response: Response | Error) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (response instanceof Error) {
        throw response;
      }
      return response;
    }),
  );
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("RequireProfileSetup", () => {
  beforeEach(() => {
    router.replace.mockReset();
  });

  it("shows the page when the resume, titles and country are set", async () => {
    respondWith(json(COMPLETE));

    render(<RequireProfileSetup>Inbox</RequireProfileSetup>);

    expect(await screen.findByText("Inbox")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it.each([
    ["no resume", { resume: null }],
    ["no desired titles", { desired_titles: [] }],
    ["no country", { country: null }],
    ["no fetch time", { fetch_time: null }],
  ])("sends the user to the Profile page with %s", async (_, patch) => {
    respondWith(json({ ...COMPLETE, ...patch }));

    render(<RequireProfileSetup>Inbox</RequireProfileSetup>);

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith("/profile"),
    );
    expect(screen.queryByText("Inbox")).not.toBeInTheDocument();
  });

  it("shows the page when the preferences cannot be loaded", async () => {
    respondWith(new TypeError("Failed to fetch"));

    render(<RequireProfileSetup>Inbox</RequireProfileSetup>);

    expect(await screen.findByText("Inbox")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
