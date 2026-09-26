import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { CompanyDetail } from "@/lib/api/companies";

import { CompanyDetails } from "./company-details";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));

const COMPANY: CompanyDetail = {
  id: 3,
  name: "Acme",
  logo_url: null,
  industries: ["Fintech"],
  growth_stage: "Series B",
  employee_estimate: "51-200",
  liked: false,
  website_url: "https://acme.example.com",
  linkedin_url: "https://www.linkedin.com/company/acme/",
  description: "Payments for small businesses.",
  history: null,
  job_count: 0,
  jobs: [],
  contacts: [],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers `GET /api/v1/companies/3` with `company` (404 when `null`) and DELETE with 204. */
function stubApi(company: CompanyDetail | null) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return company
      ? json(company)
      : json({ detail: "Company not found." }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDetails() {
  render(
    <AnnouncerProvider>
      <CompanyDetails companyId={3} />
    </AnnouncerProvider>,
  );
}

describe("CompanyDetails", () => {
  it("links to the LinkedIn page and people tab, trimming the trailing slash", async () => {
    stubApi(COMPANY);
    renderDetails();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Acme" }),
    ).toBeInTheDocument();
    const page = screen.getByRole("link", { name: /LinkedIn page/ });
    const people = screen.getByRole("link", { name: /People on LinkedIn/ });
    expect(page).toHaveAttribute("href", COMPANY.linkedin_url);
    expect(people).toHaveAttribute(
      "href",
      "https://www.linkedin.com/company/acme/people/",
    );
    expect(page).toHaveAttribute("target", "_blank");
    expect(people).toHaveAttribute("target", "_blank");
  });

  it("hides the LinkedIn links when the company has no LinkedIn URL", async () => {
    stubApi({ ...COMPANY, linkedin_url: null });
    renderDetails();

    await screen.findByRole("heading", { level: 1, name: "Acme" });
    expect(
      screen.queryByRole("link", { name: /LinkedIn/ }),
    ).not.toBeInTheDocument();
  });

  it("disables Delete with the reason while the company has jobs", async () => {
    const fetchMock = stubApi({ ...COMPANY, job_count: 2 });
    const user = userEvent.setup();
    renderDetails();

    const button = await screen.findByRole("button", { name: "Delete" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription(
      "Companies with jobs can't be deleted.",
    );
    await user.click(button);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("deletes after confirmation and returns to the Companies page", async () => {
    const fetchMock = stubApi(COMPANY);
    const user = userEvent.setup();
    renderDetails();

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog", { name: "Delete Acme?" });
    expect(dialog).toHaveTextContent("contacts will be deleted too");
    await user.click(
      within(dialog).getByRole("button", { name: "Delete company" }),
    );

    await vi.waitFor(() =>
      expect(router.push).toHaveBeenCalledWith("/companies"),
    );
    expect(fetchMock).toHaveBeenLastCalledWith("/api/v1/companies/3", {
      method: "DELETE",
      credentials: "include",
    });
  });

  it("shows a friendly page when the company does not exist", async () => {
    stubApi(null);
    renderDetails();

    expect(
      await screen.findByRole("heading", { name: "Company not found" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to Companies" }),
    ).toHaveAttribute("href", "/companies");
  });
});
