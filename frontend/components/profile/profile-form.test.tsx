import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Preferences } from "@/lib/api/preferences";

import { ProfileForm } from "./profile-form";

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

function tagList(label: string) {
  return screen.getByRole("list", { name: `${label} tags` });
}

describe("ProfileForm", () => {
  it("saves an edited field with PUT and confirms the save", async () => {
    const saved: Preferences = {
      ...EMPTY_PREFERENCES,
      desired_titles: ["Backend Engineer"],
      country: "US",
      currency: "USD",
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
    });
    expect(
      screen.queryByText("Job discovery is paused"),
    ).not.toBeInTheDocument();
  });

  it("merges resume suggestions into the tag inputs and asks for a review", async () => {
    mockApi({
      "GET /api/v1/preferences": () =>
        json({ ...EMPTY_PREFERENCES, hard_skills: ["Python"] }),
      "POST /api/v1/preferences/resume": () =>
        json({
          resume: { file_type: "pdf", uploaded_at: "2026-09-25T10:00:00Z" },
          suggestions: {
            desired_titles: ["Data Engineer"],
            hard_skills: ["python", "SQL"],
            soft_skills: [],
          },
          warning: null,
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    expect(
      await screen.findByText("Job discovery is paused"),
    ).toBeInTheDocument();
    await user.upload(
      screen.getByLabelText("Resume file"),
      new File(["%PDF-1.7"], "cv.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText("2 suggestions added from your resume"),
    ).toBeInTheDocument();
    expect(screen.getByText("PDF document")).toBeInTheDocument();
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
    await user.click(await screen.findByRole("button", { name: "Save" }));

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
    await user.type(
      await screen.findByLabelText("Minimum yearly salary"),
      "200",
    );
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
          resume: { file_type: "docx", uploaded_at: "2026-09-25T10:00:00Z" },
        }),
      "DELETE /api/v1/preferences/resume": () =>
        new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    expect(await screen.findByText("Word document")).toBeInTheDocument();
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
    expect(
      screen.getByRole("button", { name: "Upload resume" }),
    ).toBeInTheDocument();
  });

  it("rejects an oversized resume without uploading and warns when suggestions fail", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/preferences": () => json(EMPTY_PREFERENCES),
      "POST /api/v1/preferences/resume": () =>
        json({
          resume: { file_type: "pdf", uploaded_at: "2026-09-25T10:00:00Z" },
          suggestions: null,
          warning:
            "Your resume was saved, but suggestions could not be generated right now.",
        }),
    });
    const user = userEvent.setup();

    render(<ProfileForm />);
    await user.upload(
      await screen.findByLabelText("Resume file"),
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
    expect(screen.getByText("PDF document")).toBeInTheDocument();
    expect(
      screen.queryByText(
        "The resume is larger than 10 MB. Upload a smaller file.",
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/suggestions? added/)).not.toBeInTheDocument();
  });
});
