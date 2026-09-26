import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { JobCard } from "@/lib/api/jobs";

import { JobList } from "./job-list";

// A minimal URL store standing in for the App Router's search params.
const navigation = vi.hoisted(() => {
  let params = new URLSearchParams();
  const listeners = new Set<() => void>();
  return {
    params: () => params,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    set(query: string) {
      params = new URLSearchParams(query);
      listeners.forEach((listener) => listener());
    },
    replaced: [] as string[],
  };
});

vi.mock("next/navigation", async () => {
  const { useSyncExternalStore } = await import("react");
  const router = {
    replace(url: string) {
      navigation.replaced.push(url);
      navigation.set(url.split("?")[1] ?? "");
    },
  };
  return {
    usePathname: () => "/inbox/recommended",
    useRouter: () => router,
    useSearchParams: () =>
      useSyncExternalStore(navigation.subscribe, navigation.params),
  };
});

const JOB: JobCard = {
  id: 1,
  title: "Data Engineer",
  company_id: 2,
  company_name: "Globex",
  company_industries: [],
  company_growth_stage: null,
  location_city: null,
  location_state: null,
  location_country: null,
  work_arrangement: null,
  job_type_classification: null,
  seniority_level: null,
  year_exp: null,
  compensation_range: null,
  visa_sponsorship: null,
  overall_score: 72,
  evaluation_error: null,
  inbox_type: "recommended",
  liked: true,
  discovered_when: "2026-09-24T10:00:00Z",
  applied_when: null,
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

function mockJobs(pageFor: (query: URLSearchParams) => JobCard[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    return json({ items: pageFor(url.searchParams), next_cursor: null });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderList(inbox: "recommended" | "need_attention" = "recommended") {
  render(
    <AnnouncerProvider>
      <JobList inbox={inbox} />
    </AnnouncerProvider>,
  );
}

describe("JobList", () => {
  beforeEach(() => {
    navigation.set("");
    navigation.replaced.length = 0;
  });

  it("puts a changed filter in the URL and reloads from the first page", async () => {
    const fetchMock = mockJobs(() => [JOB]);
    const user = userEvent.setup();
    renderList();
    expect(await screen.findByText("Data Engineer")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Only liked" }));

    expect(navigation.replaced).toEqual(["/inbox/recommended?liked=true"]);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const lastUrl = String(fetchMock.mock.lastCall?.[0]);
    expect(lastUrl).toBe("/api/v1/jobs?inbox=recommended&liked=true");
    expect(
      screen.getByRole("checkbox", { name: "Only liked" }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("shows the friendly empty state for an empty inbox", async () => {
    mockJobs(() => []);
    renderList("need_attention");

    expect(
      await screen.findByRole("heading", {
        name: "Nothing needs your attention",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clear filters" }),
    ).not.toBeInTheDocument();
  });

  it("shows the no-match state when filters exclude every job", async () => {
    navigation.set("visa=yes&company=initech");
    mockJobs((query) => (query.get("visa") === "yes" ? [] : [JOB]));
    const user = userEvent.setup();
    renderList();

    expect(
      await screen.findByRole("heading", {
        name: "No jobs match your filters",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Search by company")).toHaveValue("initech");

    const [clear] = screen.getAllByRole("button", { name: "Clear filters" });
    await user.click(clear);

    expect(await screen.findByText("Data Engineer")).toBeInTheDocument();
    expect(navigation.params().toString()).toBe("");
    expect(screen.getByLabelText("Search by company")).toHaveValue("");
  });
});
