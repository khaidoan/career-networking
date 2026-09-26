import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";

import { CompanyForm } from "./company-form";

function renderForm(onSaved = vi.fn()) {
  render(
    <AnnouncerProvider>
      <CompanyForm
        open
        onOpenChange={() => {}}
        company={null}
        onSaved={onSaved}
      />
    </AnnouncerProvider>,
  );
  return onSaved;
}

function errorFor(label: string | RegExp) {
  const field = screen.getByLabelText(label);
  const errorId = field.getAttribute("aria-describedby")?.split(" ").at(-1);
  return errorId ? document.getElementById(errorId)?.textContent : null;
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Name"), "Acme");
  await user.type(
    screen.getByLabelText("Website URL"),
    "https://acme.example.com",
  );
  await user.type(
    screen.getByLabelText("LinkedIn URL"),
    "https://www.linkedin.com/company/acme",
  );
  await user.type(screen.getByLabelText("Description"), "Payments.");
  await user.type(screen.getByLabelText("Industries"), "Fintech{Enter}");
  await user.type(screen.getByLabelText("Growth stage"), "Series B");
  await user.type(screen.getByLabelText("Employee estimate"), "51-200");
}

describe("CompanyForm", () => {
  it("shows required-field errors without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("LinkedIn URL"), "https://x.com/a");
    await user.click(screen.getByRole("button", { name: "Add company" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(errorFor("Name")).toBe("Enter the company name.");
    expect(errorFor("Website URL")).toBe("Enter the website URL.");
    expect(errorFor("LinkedIn URL")).toBe("Enter a linkedin.com URL.");
    expect(errorFor("Industries")).toBe("Add at least one industry.");
    expect(errorFor(/Logo URL/)).toBeNull();
    expect(screen.getByLabelText("Name")).toHaveFocus();
  });

  it("shows the server's 422 messages next to the matching fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: [
              {
                loc: ["body", "website_url"],
                msg: "Value error, must be an absolute http(s) URL",
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    const onSaved = renderForm();
    const user = userEvent.setup();
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Add company" }));

    expect(
      await screen.findByText("Must be an absolute http(s) URL"),
    ).toBeInTheDocument();
    expect(errorFor("Website URL")).toBe("Must be an absolute http(s) URL");
    expect(screen.getByLabelText("Website URL")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(onSaved).not.toHaveBeenCalled();
  });
});
