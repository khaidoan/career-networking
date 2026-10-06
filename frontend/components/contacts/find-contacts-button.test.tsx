import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type {
  ContactSearchResult,
  ContactSearchStatus,
} from "@/lib/api/contacts";

import { FindContactsButton } from "./find-contacts-button";

const AVAILABLE: ContactSearchStatus = {
  available: true,
  unavailable_reason: null,
  last_searched_at: null,
};

function result(created: number, updated: number): ContactSearchResult {
  return {
    found: created + updated,
    created,
    updated,
    contacts: [],
    contact_search: { ...AVAILABLE, last_searched_at: "2026-09-25T12:00:00Z" },
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderButton(
  status: ContactSearchStatus = AVAILABLE,
  peopleUrl?: string,
) {
  const onFound = vi.fn();
  render(
    <AnnouncerProvider>
      <FindContactsButton
        companyId={3}
        jobId={7}
        status={status}
        onFound={onFound}
        peopleUrl={peopleUrl}
      />
    </AnnouncerProvider>,
  );
  return {
    onFound,
    button: screen.getByRole("button", { name: "Find contacts" }),
  };
}

function politeRegion() {
  return document.querySelector('[aria-live="polite"]');
}

describe("FindContactsButton", () => {
  it("is enabled when contact search is available", () => {
    const { button } = renderButton();

    expect(button).toHaveAccessibleName("Find contacts");
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByText(/searched/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("offers Browse on LinkedIn next to Find contacts", () => {
    const { button } = renderButton(
      AVAILABLE,
      "https://www.linkedin.com/company/acme/people/",
    );

    const link = screen.getByRole("link", {
      name: /^Browse on LinkedIn/,
    });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.parentElement).toBe(button.parentElement);
  });

  it.each([
    ["no_api_key", /needs a SerpApi key\. See Contact search in the README/],
    ["no_eligible_job", /companies with a recommended or applied job/],
  ] as const)(
    "is disabled but focusable with a linked explanation for %s",
    async (reason, explanation) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const user = userEvent.setup();
      const { button } = renderButton({
        available: false,
        unavailable_reason: reason,
        last_searched_at: null,
      });

      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAccessibleDescription(explanation);
      expect(screen.getByText(explanation)).toBeVisible();

      await user.tab();
      expect(button).toHaveFocus();
      await user.keyboard("{Enter}");
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("shows Searching…, ignores extra clicks and announces the counts", async () => {
    let answer: (response: Response) => void = () => {};
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          answer = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { onFound, button } = renderButton();

    await user.click(button);
    expect(button).toHaveAccessibleName("Searching…");
    expect(button).toHaveAttribute("aria-disabled", "true");
    await user.keyboard("{Enter}");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/companies/3/contacts/search?job_id=7",
      expect.objectContaining({ method: "POST" }),
    );

    answer(json(result(3, 1)));
    expect(await screen.findByText("Find contacts")).toBeVisible();
    expect(onFound).toHaveBeenCalledWith(result(3, 1));
    const found = "Found 3 new contacts (1 contact updated).";
    expect(politeRegion()).toHaveTextContent(found);
    // The outcome also stays on the page until the next search.
    expect(screen.getByText(found, { selector: "p" })).toBeVisible();

    fetchMock.mockImplementation(() => Promise.resolve(json(result(0, 2))));
    await user.click(button);
    expect(
      await screen.findByText(
        "No new contacts: everyone found is already in your list (2 contacts updated).",
        { selector: "p" },
      ),
    ).toBeVisible();

    fetchMock.mockImplementation(() => Promise.resolve(json(result(0, 0))));
    await user.click(button);
    expect(
      await screen.findByText(
        "No matching people were found on LinkedIn for this company and role.",
        { selector: "p" },
      ),
    ).toBeVisible();
  });

  it("announces the API's error message and keeps it on the page to copy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              detail:
                "Contact search failed: the search service could not be reached. Try again later.",
            },
            502,
          ),
        ),
      ),
    );
    const user = userEvent.setup();
    const { onFound, button } = renderButton();

    await user.click(button);

    await waitFor(() =>
      expect(
        document.querySelector('[aria-live="assertive"]'),
      ).toHaveTextContent(
        "Could not find contacts. Contact search failed: the search service could not be reached.",
      ),
    );
    expect(onFound).not.toHaveBeenCalled();

    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Could not find contacts.");
    await user.click(within(alert).getByRole("button", { name: "Copy error" }));
    expect(writeText).toHaveBeenCalledWith(
      "Could not find contacts. Contact search failed: the search service could not be reached. Try again later.",
    );
    expect(within(alert).getByRole("button", { name: "Copied" })).toBeVisible();
  });
});
