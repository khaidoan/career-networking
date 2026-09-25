import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TopBar } from "./top-bar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/inbox/recommended",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

describe("TopBar", () => {
  it("shows the user's initials from /auth/me and a Logout item in the avatar menu", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          username: "admin",
          first_name: "Jane",
          last_name: "Doe",
          initials: "JD",
          email: "jane.doe@example.com",
        }),
      ),
    );
    const user = userEvent.setup();

    render(<TopBar />);

    expect(
      screen.getByRole("link", { name: "Career Networking" }),
    ).toHaveAttribute("href", "/inbox/recommended");
    expect(await screen.findByText("JD")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/auth/me",
      expect.objectContaining({ credentials: "include" }),
    );

    await user.click(
      screen.getByRole("button", { name: "Account menu for Jane Doe" }),
    );

    expect(
      await screen.findByRole("menuitem", { name: "Logout" }),
    ).toBeInTheDocument();
  });
});
