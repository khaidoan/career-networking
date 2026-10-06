import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Preferences } from "@/lib/api/preferences";

import { ProfileForm } from "./profile-form";

const detected = vi.hoisted(() => ({
  country: undefined as string | undefined,
}));

// The real detection reads the test machine's time zone.
vi.mock("@/lib/profile/detect-country", () => ({
  detectCountry: () => detected.country,
}));
vi.mock("@/lib/profile/timezones", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/profile/timezones")>()),
  browserTimeZone: () => "America/Chicago",
}));

const EMPTY_PREFERENCES: Preferences = {
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

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes mocked `fetch` calls by method and path; unexpected calls fail the test. */
function mockApi(
  routes: Record<string, (init: RequestInit) => Response | Promise<Response>>,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const key = `${init.method ?? "GET"} ${String(input)}`;
      const handler = routes[key];
      if (!handler) {
        throw new Error(`Unexpected request: ${key}`);
      }
      return handler(init);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const RESUME = {
  file_type: "pdf",
  file_name: "Jane Doe CV.pdf",
  uploaded_at: "2026-09-25T10:00:00Z",
} as const;

/** Closes the setup dialog that opens while the resume, titles or country are missing. */
async function dismissSetup(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Ok" }));
}

function tagList(label: string) {
  return screen.getByRole("list", { name: `${label} tags` });
}

describe("ProfileForm", () => {
  beforeEach(() => {
    detected.country = undefined;
  });

  // The first test in this file pays the cold first mount of the whole form, whose Country and
  // Currency selects hold ~400 Radix items. That takes ~0.7s alone but ~2.5s when the full suite
  // runs in parallel, so the 5s default left little headroom; 10s keeps a real hang visible.
  it("saves an edited field with PUT and confirms the save", async () => {
    const saved: Preferences = {
      ...EMPTY_PREFERENCES,
      desired_titles: ["Backend Engineer"],
      country: "US",
      currency: "USD",
      resume: RESUME,
    };
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () => json(saved),
      "PUT /api/v1/preferences": (init) =>
        json({ ...saved, ...JSON.parse(String(init.body)) }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Choose the daily time (and time zone) to fetch new jobs."]);
    await dismissSetup(user);
    await user.type(screen.getByLabelText("Hard skills"), "Python{Enter}");
    await user.type(
      screen.getByLabelText("Excluded title words"),
      "QA, Site Reliability{Enter}",
    );
    await user.type(screen.getByLabelText("Minimum yearly salary"), "120000");
    expect(
      screen.getByRole("combobox", { name: "Time zone" }),
    ).toHaveAccessibleDescription(
      "Detected from your browser. Check it, then click Save.",
    );
    fireEvent.change(screen.getByLabelText("Daily job fetch time"), {
      target: { value: "07:30" },
    });
    await user.type(
      screen.getByLabelText("Additional Information"),
      "Notice period: 4 weeks.",
    );
    const autoApply = screen.getByRole("checkbox", { name: "Auto apply" });
    expect(autoApply).not.toBeChecked();
    await user.click(autoApply);
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Your profile was saved."),
    ).toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put?.[1]).toMatchObject({ credentials: "include" });
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
      desired_titles: ["Backend Engineer"],
      excluded_title_words: ["QA", "Site Reliability"],
      hard_skills: ["Python"],
      country: "US",
      currency: "USD",
      salary_min: 120000,
      salary_max: null,
      auto_apply: true,
      fetch_time: "07:30",
      fetch_timezone: "America/Chicago",
      additional_information: "Notice period: 4 weeks.",
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Jane Doe CV.pdf")).toBeInTheDocument();
  }, 10_000);

  it("merges resume suggestions into the tag inputs and asks for a review", async () => {
    mockApi({
      "GET /api/v1/preferences": () =>
        json({ ...EMPTY_PREFERENCES, hard_skills: ["Python"] }),
      "POST /api/v1/preferences/resume": () =>
        json({
          resume: { ...RESUME, file_name: "cv.pdf" },
          suggestions: {
            desired_titles: ["Data Engineer"],
            hard_skills: ["python", "SQL"],
            soft_skills: [],
          },
          warning: null,
          preferences: {
            ...EMPTY_PREFERENCES,
            desired_titles: ["Data Engineer"],
            hard_skills: ["Python", "SQL"],
            resume: { ...RESUME, file_name: "cv.pdf" },
          },
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    const dialog = await screen.findByRole("dialog", {
      name: "Finish setting up your profile",
    });
    expect(
      within(dialog)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([
      "Upload your resume (PDF or Word).",
      "Add at least one desired job title.",
      "Choose the country you want to work in.",
      "Choose the daily time (and time zone) to fetch new jobs.",
    ]);
    await dismissSetup(user);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.upload(
      screen.getByLabelText("Resume file"),
      new File(["%PDF-1.7"], "cv.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText("2 suggestions added from your resume"),
    ).toBeInTheDocument();
    expect(screen.getByText("cv.pdf")).toBeInTheDocument();
    const skills = within(tagList("Hard skills"));
    // "python" duplicates the saved "Python" and is not added twice.
    expect(
      skills.getAllByRole("listitem").map((item) => item.textContent),
    ).toEqual(["Python", "SQL(suggested)"]);
    expect(
      within(tagList("Desired job titles")).getByText("(suggested)"),
    ).toBeInTheDocument();
  });

  it("shows field-level errors from a 422 response", async () => {
    mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
      "PUT /api/v1/preferences": () =>
        json(
          {
            detail: [
              {
                type: "value_error",
                loc: ["body", "country"],
                msg: "Value error, is not one of the allowed options",
              },
              {
                type: "value_error",
                loc: ["body", "eeo_answers", "veteran_status"],
                msg: "Value error, is not one of the allowed options",
              },
            ],
          },
          422,
        ),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        "Some fields need your attention. Check the messages below.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Country")).toHaveAccessibleDescription(
      "Is not one of the allowed options",
    );
    expect(screen.getByLabelText("Veteran status")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("blocks saving when the minimum salary is above the maximum", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);
    await user.type(screen.getByLabelText("Minimum yearly salary"), "200");
    await user.type(screen.getByLabelText("Maximum yearly salary"), "100");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        "Must be greater than or equal to the minimum salary.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("deletes the resume only after confirmation and keeps titles and skills", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () =>
        json({
          ...EMPTY_PREFERENCES,
          desired_titles: ["Backend Engineer"],
          country: "US",
          fetch_time: "06:00",
          fetch_timezone: "UTC",
          resume: { ...RESUME, file_type: "docx", file_name: "CV final.docx" },
        }),
      "DELETE /api/v1/preferences/resume": () =>
        new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    expect(await screen.findByText("CV final.docx")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    // One resume at a time: there is no upload (or replace) while one is saved.
    expect(
      screen.queryByRole("button", { name: /upload resume|replace resume/i }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    await user.click(screen.getByRole("button", { name: "Delete resume" }));

    expect(
      await screen.findByText("No resume uploaded yet."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/preferences/resume",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    );
    expect(
      within(tagList("Desired job titles")).getByText("Backend Engineer"),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Country" })).toHaveValue(
      "United States",
    );
    expect(
      screen.getByRole("button", { name: "Upload resume" }),
    ).toBeInTheDocument();
  });

  it("rejects an oversized resume without uploading and warns when suggestions fail", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
      "POST /api/v1/preferences/resume": () =>
        json({
          resume: { ...RESUME, file_name: "cv.pdf" },
          suggestions: null,
          warning:
            "Your resume was saved, but suggestions could not be generated right now.",
          preferences: {
            ...EMPTY_PREFERENCES,
            resume: { ...RESUME, file_name: "cv.pdf" },
          },
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);
    await user.upload(
      screen.getByLabelText("Resume file"),
      new File([new Uint8Array(10 * 1024 * 1024 + 1)], "big.pdf", {
        type: "application/pdf",
      }),
    );

    expect(
      await screen.findByText(
        "The resume is larger than 10 MB. Upload a smaller file.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.upload(
      screen.getByLabelText("Resume file"),
      new File(["%PDF-1.7"], "cv.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText(
        "Your resume was saved, but suggestions could not be generated right now.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("cv.pdf")).toBeInTheDocument();
    expect(
      screen.queryByText(
        "The resume is larger than 10 MB. Upload a smaller file.",
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/suggestions? added/)).not.toBeInTheDocument();
  });

  it("pre-fills a detected country and its currency until a country is saved", async () => {
    detected.country = "CA";
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
      "PUT /api/v1/preferences": (init) =>
        json({ ...EMPTY_PREFERENCES, ...JSON.parse(String(init.body)) }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);

    const country = screen.getByRole("combobox", { name: "Country" });
    expect(country).toHaveValue("Canada");
    expect(country).toHaveAccessibleDescription(
      "Detected from your browser. Check it, then click Save.",
    );
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Your profile was saved."),
    ).toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
      country: "CA",
      currency: "CAD",
    });
    expect(country).not.toHaveAccessibleDescription();
  });

  it("shows the seniority, country and address the server took from the resume", async () => {
    detected.country = "CA";
    mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
      "POST /api/v1/preferences/resume": () =>
        json({
          resume: RESUME,
          suggestions: {
            desired_titles: ["Data Engineer"],
            hard_skills: [],
            soft_skills: [],
            seniority: ["senior"],
            country: "GB",
            address: "1 King Street, London",
          },
          warning: null,
          preferences: {
            ...EMPTY_PREFERENCES,
            desired_titles: ["Data Engineer"],
            seniority: ["senior"],
            country: "GB",
            currency: "GBP",
            address: "1 King Street, London",
            resume: RESUME,
          },
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);
    expect(screen.getByRole("combobox", { name: "Country" })).toHaveValue(
      "Canada",
    );
    await user.upload(
      screen.getByLabelText("Resume file"),
      new File(["%PDF-1.7"], "cv.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByText("Jane Doe CV.pdf")).toBeInTheDocument();
    const country = screen.getByRole("combobox", { name: "Country" });
    expect(country).toHaveValue("United Kingdom");
    // Saved now, so the "detected from your browser" hint is gone.
    expect(country).not.toHaveAccessibleDescription();
    expect(screen.getByLabelText("Currency")).toHaveTextContent("GBP");
    expect(screen.getByRole("checkbox", { name: "Senior" })).toBeChecked();
    expect(screen.getByLabelText("Address")).toHaveValue(
      "1 King Street, London",
    );
  });

  it("shows the saved fetch time and time zone and requires a time", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () =>
        json({
          ...EMPTY_PREFERENCES,
          desired_titles: ["Backend Engineer"],
          country: "US",
          resume: RESUME,
          fetch_time: "21:15",
          fetch_timezone: "Asia/Calcutta",
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    const time = await screen.findByLabelText("Daily job fetch time");
    expect(time).toHaveValue("21:15");
    // A legacy name the browser's list may lack is still shown, not detected.
    const zone = screen.getByRole("combobox", { name: "Time zone" });
    expect(zone).toHaveValue("Asia/Calcutta");
    expect(zone).toHaveAccessibleDescription(
      "The fetch time is in this time zone.",
    );

    fireEvent.change(time, { target: { value: "" } });
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Enter a time, for example 06:00."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("says whether job fetching is enabled, from the saved profile", async () => {
    const saved: Preferences = {
      ...EMPTY_PREFERENCES,
      desired_titles: ["Backend Engineer"],
      country: "US",
      resume: RESUME,
      job_fetching: {
        enabled: false,
        missing: ["fetch_time", "fetch_timezone"],
        next_run_at: null,
      },
    };
    mockApi({
      "GET /api/v1/preferences": () => json(saved),
      "PUT /api/v1/preferences": (init) =>
        json({
          ...saved,
          ...JSON.parse(String(init.body)),
          job_fetching: {
            enabled: true,
            missing: [],
            next_run_at: "2026-10-07T13:00:00Z",
          },
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await dismissSetup(user);

    expect(screen.getByText("Job fetching is disabled")).toBeInTheDocument();
    expect(
      screen.getByText(
        "To turn it on, fill in and save: Daily job fetch time, Time zone.",
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Job fetching is enabled"),
    ).toBeInTheDocument();
    // 13:00 UTC is 08:00 in Chicago (CDT); shown in the saved time zone.
    expect(screen.getByText(/^Next run: .*8:00/)).toBeInTheDocument();
  });
});
