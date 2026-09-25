import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SidebarNav } from "./sidebar-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/inbox/applied",
}));

describe("SidebarNav", () => {
  it("marks only the current route's link with aria-current=page", () => {
    render(<SidebarNav />);

    expect(screen.getByRole("link", { name: "Applied" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Recommended" }),
    ).not.toHaveAttribute("aria-current");
    expect(screen.getAllByRole("link")).toHaveLength(9);
  });
});
