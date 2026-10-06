import { render, screen, within } from "@testing-library/react";
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

const EMPTY_PREFERENCES: Preferences = {
  desired_titles: [],
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
  auto_apply: false,
  resume: null,
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
    await user.type(
      await screen.findByLabelText("Hard skills"),
      "Python{Enter}",
    );
    await user.type(screen.getByLabelText("Minimum yearly salary"), "120000");
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
      hard_skills: ["Python"],
      country: "US",
      currency: "USD",
      salary_min: 120000,
      salary_max: null,
      auto_apply: true,
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

  it("shows the seniority and country the server took from the resume", async () => {
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
          },
          warning: null,
          preferences: {
            ...EMPTY_PREFERENCES,
            desired_titles: ["Data Engineer"],
            seniority: ["senior"],
            country: "GB",
            currency: "GBP",
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
  });
});
