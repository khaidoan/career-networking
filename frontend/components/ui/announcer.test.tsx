import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnouncerProvider, useAnnounce } from "./announcer";

function CopyButton() {
  const announce = useAnnounce();
  return (
    <button type="button" onClick={() => announce("Message copied")}>
      Copy
    </button>
  );
}

describe("AnnouncerProvider", () => {
  it("announces a message politely and shows a toast without taking focus", async () => {
    const user = userEvent.setup();
    render(
      <AnnouncerProvider>
        <CopyButton />
      </AnnouncerProvider>,
    );
    const button = screen.getByRole("button", { name: "Copy" });

    await user.click(button);

    const politeRegion = document.querySelector('[aria-live="polite"]');
    expect(politeRegion).toHaveTextContent("Message copied");
    expect(screen.getByTestId("toasts")).toHaveTextContent("Message copied");
    expect(button).toHaveFocus();
  });

  it("keeps an error toast until it is dismissed, with selectable text and a Copy button", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    function Fail() {
      const announce = useAnnounce();
      return (
        <button
          type="button"
          onClick={() => announce("Save failed: 502", "error")}
        >
          Save
        </button>
      );
    }
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    // After setup, which installs its own clipboard stub.
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <AnnouncerProvider>
        <Fail />
      </AnnouncerProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));
    vi.advanceTimersByTime(60_000);

    const toasts = within(screen.getByTestId("toasts"));
    expect(toasts.getByText("Save failed: 502")).toBeVisible();
    await user.click(toasts.getByRole("button", { name: "Copy error" }));
    expect(writeText).toHaveBeenCalledWith("Save failed: 502");
    await user.click(toasts.getByRole("button", { name: "Dismiss" }));
    expect(toasts.queryByText("Save failed: 502")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
