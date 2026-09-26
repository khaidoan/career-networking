import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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
});
