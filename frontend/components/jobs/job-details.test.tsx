import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { JobDetail } from "@/lib/api/jobs";
import { formatDate } from "@/lib/jobs/format";

import { JobDetails } from "./job-details";

const JOB: JobDetail = {
  id: 7,
  title: "Backend Engineer",
  company_id: 3,
  company_name: "Acme",
  company_industries: ["Fintech"],
  company_growth_stage: "Series B",
  location_city: "Austin",
  location_state: "TX",
  location_country: "US",
  work_arrangement: "hybrid",
  job_type_classification: "full_time",
  seniority_level: "senior",
  year_exp: 5,
  compensation_range: null,
  visa_sponsorship: true,
  overall_score: 86,
  evaluation_error: null,
  inbox_type: "recommended",
  liked: false,
  discovered_when: "2026-09-24T10:00:00Z",
  applied_when: null,
  url: "https://jobs.example.com/7",
  source: "greenhouse",
  description: "About the role\nBuild <b>APIs</b>.",
  experience_score: 80,
  skill_score: 90,
  industry_exp_score: 70,
  company: {
    id: 3,
    name: "Acme",
    logo_url: null,
    industries: ["Fintech"],
    growth_stage: "Series B",
    employee_estimate: "51-200",
    liked: false,
    website_url: "https://acme.example.com",
    linkedin_url: null,
    description: "Payments for small businesses.",
    history: null,
  },
  contacts: [],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers `GET /api/v1/jobs/7` with `job` and `POST .../apply` with `applied`. */
function stubApi(
  job: JobDetail | null,
  applied: JobDetail | null = null,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && url === "/api/v1/jobs/7/apply") {
      return Promise.resolve(json(applied));
    }
    return Promise.resolve(
      job ? json(job) : json({ detail: "Job not found." }, 404),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDetails() {
  return render(
    <AnnouncerProvider>
      <JobDetails jobId={7} />
    </AnnouncerProvider>,
  );
}

function applyCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/apply"));
}

describe("JobDetails", () => {
  it("shows the four labelled scores", async () => {
    stubApi(JOB);
    renderDetails();

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Backend Engineer",
      }),
    ).toBeInTheDocument();
    const scores = within(screen.getByRole("region", { name: "Scores" }));
    for (const [label, value] of [
      ["Overall match", "86"],
      ["Experience", "80"],
      ["Skills", "90"],
      ["Industry experience", "70"],
    ]) {
      const term = scores.getByText(label, { selector: "dt" });
      expect(term.nextElementSibling).toHaveTextContent(value);
    }
    expect(scores.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the evaluation error in place of the scores", async () => {
    stubApi({
      ...JOB,
      overall_score: null,
      experience_score: null,
      skill_score: null,
      industry_exp_score: null,
      evaluation_error: "The model timed out",
    });
    renderDetails();

    const scores = within(
      await screen.findByRole("region", { name: "Scores" }),
    );
    const alert = scores.getByRole("alert");
    expect(alert).toHaveTextContent("Not scored");
    expect(alert).toHaveTextContent("The model timed out");
    expect(scores.queryByText("Overall match")).not.toBeInTheDocument();
  });

  it("renders the description as plain text with its line breaks", async () => {
    stubApi(JOB);
    renderDetails();

    const section = await screen.findByRole("region", {
      name: "Job description",
    });
    const text = within(section).getByText(/About the role/);
    expect(text.textContent).toBe("About the role\nBuild <b>APIs</b>.");
    expect(text).toHaveClass("whitespace-pre-line");
    expect(section.querySelector("b")).toBeNull();
  });

  it("marks the job applied only after the user confirms Yes", async () => {
    const appliedJob: JobDetail = {
      ...JOB,
      inbox_type: "applied",
      applied_when: "2026-09-25T12:00:00Z",
    };
    const fetchMock = stubApi(JOB, appliedJob);
    const openMock = vi.fn(() => null);
    vi.stubGlobal("open", openMock);
    const user = userEvent.setup();
    renderDetails();

    const apply = await screen.findByRole("button", { name: "Apply" });
    await user.click(apply);
    expect(openMock).toHaveBeenCalledWith(
      JOB.url,
      "_blank",
      "noopener,noreferrer",
    );
    await user.click(
      within(screen.getByRole("dialog", { name: "Did you apply?" })).getByRole(
        "button",
        { name: "No" },
      ),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(apply);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(applyCalls(fetchMock)).toHaveLength(0);

    await user.click(apply);
    await user.click(screen.getByRole("button", { name: /Yes/ }));

    expect(
      await screen.findByText(
        `Applied on ${formatDate(appliedJob.applied_when)}`,
      ),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /View posting/ })).toHaveAttribute(
      "href",
      JOB.url,
    );
    expect(applyCalls(fetchMock)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent(
      "Backend Engineer marked as applied and moved to Applied.",
    );
  });

  it("shows a friendly not-found page on 404", async () => {
    stubApi(null);
    renderDetails();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Job not found" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to inboxes" }),
    ).toHaveAttribute("href", "/inbox/recommended");
  });
});
