import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { JobCard as JobCardData } from "@/lib/api/jobs";

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
  score_explanation: null,
  evaluation_error: null,
  inbox_type: "recommended",
  liked: false,
  posted_at: null,
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

  it("shows Not scored with the reason and no Re-evaluate button", () => {
    const failed = {
      ...JOB,
      overall_score: null,
      evaluation_error: "The model timed out",
      visa_sponsorship: null,
      inbox_type: "ignored" as const,
    };
    const card = renderCard(failed, vi.fn());

    expect(card.getByText("Not scored")).toBeInTheDocument();
    expect(card.getByText("The model timed out")).toBeInTheDocument();
    expect(card.queryByText(/Visa sponsorship/)).not.toBeInTheDocument();
    expect(card.queryByText(/Match strength/)).not.toBeInTheDocument();
    expect(card.queryByRole("button", { name: /Re-evaluat/ })).toBeNull();
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

  it("shows when the job was posted, falling back to when it was found", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 26, 12));
    try {
      expect(
        renderCard({
          ...JOB,
          posted_at: new Date(2026, 8, 24, 9).toISOString(),
        }).getByText(/Posted/),
      ).toHaveTextContent("Posted 2 days ago");
      cleanup();
      expect(
        renderCard({
          ...JOB,
          discovered_when: new Date(2026, 8, 26, 8).toISOString(),
        }).getByText(/Found/),
      ).toHaveTextContent("Found today");
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens the score explanation from a scored job in Ignored only", async () => {
    const user = userEvent.setup();
    const card = renderCard({
      ...JOB,
      inbox_type: "ignored",
      overall_score: 42,
      score_explanation: "You lack the required Go experience.",
    });

    await user.click(card.getByRole("button", { name: /View Explanation/ }));

    const dialog = await screen.findByRole("dialog", {
      name: "Why this job scored low",
    });
    expect(dialog).toHaveTextContent("You lack the required Go experience.");
    expect(dialog).toHaveTextContent("Weak");
  });

  it("has no explanation button outside Ignored", () => {
    const card = renderCard(JOB);
    expect(
      card.queryByRole("button", { name: /View Explanation/ }),
    ).not.toBeInTheDocument();
  });
});
