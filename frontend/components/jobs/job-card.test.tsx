import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { JobCard as JobCardData, JobDetail } from "@/lib/api/jobs";

import { JobCard } from "./job-card";

const JOB: JobCardData = {
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
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCard(job: JobCardData, onChange = vi.fn()) {
  render(
    <AnnouncerProvider>
      <ul>
        <JobCard job={job} onChange={onChange} />
      </ul>
    </AnnouncerProvider>,
  );
  return within(screen.getByRole("listitem"));
}

describe("JobCard", () => {
  it("shows known fields with the match strength label and hides unknown ones", () => {
    const card = renderCard(JOB);

    expect(
      card.getByRole("link", { name: "Backend Engineer" }),
    ).toHaveAttribute("href", "/jobs/7");
    for (const text of [
      "Acme",
      "Fintech",
      "Series B",
      "Austin, TX, US",
      "Hybrid",
      "Full-time",
      "Senior",
      "5+ years experience",
      "Visa sponsorship",
    ]) {
      expect(card.getByText(text)).toBeInTheDocument();
    }
    expect(card.getByText(/Strong/)).toHaveTextContent(
      "Match strength: Strong·, score86",
    );
    expect(card.queryByText("Salary range")).not.toBeInTheDocument();
    expect(card.queryByText("Not scored")).not.toBeInTheDocument();
  });

  it("shows Not scored with the reason and re-evaluates the job in place", async () => {
    const failed = {
      ...JOB,
      overall_score: null,
      evaluation_error: "The model timed out",
      visa_sponsorship: null,
      inbox_type: "ignored" as const,
    };
    const rescored: JobDetail = {
      ...JOB,
      inbox_type: "recommended",
      url: "https://jobs.example.com/7",
      source: "greenhouse",
      description: null,
      experience_score: 80,
      skill_score: 90,
      industry_exp_score: 70,
      company: {
        id: 3,
        name: "Acme",
        logo_url: null,
        industries: ["Fintech"],
        growth_stage: "Series B",
        employee_estimate: null,
        liked: false,
        website_url: null,
        linkedin_url: null,
        description: null,
        history: null,
      },
      contacts: [],
    };
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
    );
    const onChange = vi.fn();
    const user = userEvent.setup();
    const card = renderCard(failed, onChange);

    expect(card.getByText("Not scored")).toBeInTheDocument();
    expect(card.getByText("The model timed out")).toBeInTheDocument();
    expect(card.queryByText(/Visa sponsorship/)).not.toBeInTheDocument();
    expect(card.queryByText(/Match strength/)).not.toBeInTheDocument();

    await user.click(card.getByRole("button", { name: "Re-evaluate" }));
    expect(
      card.getByRole("button", { name: "Re-evaluating…" }),
    ).toHaveAttribute("aria-disabled", "true");
    finish(json(rescored));

    await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith(rescored));
    expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent(
      "Backend Engineer re-evaluated: Strong match, 86. Moved to Recommended.",
    );
  });

  it("likes optimistically and rolls back with an announced error when saving fails", async () => {
    let finish: (response: Response) => void = () => {};
    const fetchMock = vi.fn(
      () => new Promise<Response>((resolve) => (finish = resolve)),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onChange = vi.fn();
    const user = userEvent.setup();
    const card = renderCard(JOB, onChange);
    const heart = card.getByRole("button", { name: "Like Backend Engineer" });

    await user.click(heart);
    expect(heart).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/jobs/7",
      expect.objectContaining({ method: "PATCH", body: '{"liked":true}' }),
    );

    finish(json({ detail: "An unexpected error occurred." }, 500));
    await vi.waitFor(() =>
      expect(heart).toHaveAttribute("aria-pressed", "false"),
    );
    expect(onChange).not.toHaveBeenCalled();
    expect(document.querySelector('[aria-live="assertive"]')).toHaveTextContent(
      "Could not like Backend Engineer. Something went wrong. Please try again.",
    );
  });

  it("moves focus to the job title once a successful re-evaluation removes the button", async () => {
    const failed = {
      ...JOB,
      overall_score: null,
      evaluation_error: "Timed out",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ ...JOB, overall_score: 72 })),
    );
    function Harness() {
      const [job, setJob] = useState<JobCardData>(failed);
      return (
        <AnnouncerProvider>
          <ul>
            <JobCard job={job} onChange={setJob} />
          </ul>
        </AnnouncerProvider>
      );
    }
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Re-evaluate" }));

    const title = screen.getByRole("link", { name: "Backend Engineer" });
    await vi.waitFor(() => expect(title).toHaveFocus());
    expect(
      screen.queryByRole("button", { name: /Re-evaluat/ }),
    ).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("listitem")).getByText(/Good/),
    ).toBeInTheDocument();
  });
});
