import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { Contact } from "@/lib/api/contacts";
import { buildConnectionMessage } from "@/lib/outreach/message";

import { ContactList } from "./contact-list";

const CONTACT: Contact = {
  id: 11,
  company_id: 3,
  name: "Jane Doe",
  first_name: "Jane",
  last_name: "Doe",
  title: "Engineering Manager",
  linkedin_url: "https://www.linkedin.com/in/jane-doe",
  connection_request_sent: false,
  connection_request_sent_at: null,
};

const MESSAGE = buildConnectionMessage({
  firstName: "Jane",
  jobTitle: "Backend Engineer",
  companyName: "Acme",
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// jsdom cannot open tabs; stop the link's default navigation after React's handler has run.
function blockNavigation(event: MouseEvent) {
  event.preventDefault();
}

function setup(jobTitle: string | null = "Backend Engineer") {
  const user = userEvent.setup();
  const writeText = vi.fn(() => Promise.resolve());
  // `userEvent.setup()` installs its own clipboard stub; replace it with a spy.
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      json({
        ...CONTACT,
        connection_request_sent: true,
        connection_request_sent_at: "2026-09-25T12:00:00Z",
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  render(
    <AnnouncerProvider>
      <ContactList
        contacts={[CONTACT]}
        companyName="Acme"
        jobTitle={jobTitle}
      />
    </AnnouncerProvider>,
  );
  const link = screen.getByRole("link", { name: /Jane Doe/ });
  return { user, writeText, fetchMock, link };
}

describe("ContactList", () => {
  beforeEach(() => document.addEventListener("click", blockNavigation));
  afterEach(() => document.removeEventListener("click", blockNavigation));

  it("opens LinkedIn, copies the message and marks the request as sent in one click", async () => {
    const { user, writeText, fetchMock, link } = setup();

    expect(link).toHaveAttribute("href", CONTACT.linkedin_url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.queryByText("Request sent")).not.toBeInTheDocument();

    await user.click(link);

    expect(writeText).toHaveBeenCalledWith(MESSAGE);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/contacts/11/connection-request",
      expect.objectContaining({ method: "POST" }),
    );
    expect(await screen.findByText("Request sent")).toBeInTheDocument();
    expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent(
      "Message copied",
    );
    expect(screen.getByTestId("toasts")).toHaveTextContent("Message copied");
  });

  it("shows the message in a copy dialog when the Clipboard API fails", async () => {
    const { user, writeText, fetchMock, link } = setup();
    writeText.mockImplementation(() =>
      Promise.reject(new DOMException("Denied", "NotAllowedError")),
    );

    await user.click(link);

    const dialog = await screen.findByRole("dialog", {
      name: "Copy your connection message",
    });
    expect(
      within(dialog).getByRole("textbox", { name: "Connection message" }),
    ).toHaveValue(MESSAGE);
    expect(within(dialog).getByRole("button", { name: "Copy" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("notes that contacts may be out of date, and prompts a search when empty", () => {
    const { rerender } = render(
      <ContactList contacts={[CONTACT]} companyName="Acme" jobTitle={null} />,
    );
    expect(
      screen.getByText("Found via search, may be out of date."),
    ).toBeVisible();

    rerender(
      <ContactList
        contacts={[]}
        companyName="Acme"
        jobTitle={null}
        contactSearch={{
          available: true,
          unavailable_reason: null,
          last_searched_at: null,
        }}
      />,
    );
    expect(
      screen.getByText(
        "Select Find contacts to look for people at Acme on LinkedIn.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText("Found via search, may be out of date."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/later phase/)).not.toBeInTheDocument();

    rerender(
      <ContactList
        contacts={[]}
        companyName="Acme"
        jobTitle={null}
        contactSearch={{
          available: false,
          unavailable_reason: "no_eligible_job",
          last_searched_at: null,
        }}
      />,
    );
    expect(
      screen.getByText(/once one of its jobs is recommended or applied to/),
    ).toBeVisible();
  });

  it("only opens LinkedIn when there is no job to mention", async () => {
    const { user, writeText, fetchMock, link } = setup(null);

    await user.click(link);

    expect(link).toHaveAttribute("href", CONTACT.linkedin_url);
    expect(writeText).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByText("Request sent")).not.toBeInTheDocument();
  });
});
