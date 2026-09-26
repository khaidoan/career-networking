import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnnouncerProvider } from "@/components/ui/announcer";
import type { CompanyCard } from "@/lib/api/companies";

import { CompanyList } from "./company-list";

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
    usePathname: () => "/companies",
    useRouter: () => router,
    useSearchParams: () =>
      useSyncExternalStore(navigation.subscribe, navigation.params),
  };
});

const ACME: CompanyCard = {
  id: 3,
  name: "Acme",
  logo_url: null,
  industries: ["Fintech"],
  growth_stage: "Series B",
  employee_estimate: "51-200",
  liked: false,
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers the industries call and every list call (with `ACME`), recording list URLs. */
function stubApi() {
  const listUrls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/companies/industries") {
        return json(["Fintech", "Healthcare"]);
      }
      listUrls.push(url);
      return json({ items: [ACME], next_cursor: null });
    }),
  );
  return listUrls;
}

describe("CompanyList", () => {
  beforeEach(() => {
    navigation.set("");
    navigation.replaced.length = 0;
  });

  it("puts the search and the industry filter in the URL and reloads the list", async () => {
    const listUrls = stubApi();
    const user = userEvent.setup();
    render(
      <AnnouncerProvider>
        <CompanyList />
      </AnnouncerProvider>,
    );
    expect(
      await screen.findByRole("link", { name: "Acme" }),
    ).toBeInTheDocument();
    expect(listUrls).toEqual(["/api/v1/companies"]);

    await user.type(screen.getByLabelText("Search by name"), "acme");
    await vi.waitFor(() =>
      expect(navigation.replaced).toEqual(["/companies?q=acme"]),
    );
    await vi.waitFor(() =>
      expect(listUrls.at(-1)).toBe("/api/v1/companies?q=acme"),
    );

    await user.click(screen.getByRole("button", { name: /Industry/ }));
    await user.click(
      await screen.findByRole("menuitemcheckbox", { name: "Healthcare" }),
    );

    expect(navigation.replaced.at(-1)).toBe(
      "/companies?q=acme&industry=Healthcare",
    );
    await vi.waitFor(() =>
      expect(listUrls.at(-1)).toBe(
        "/api/v1/companies?q=acme&industry=Healthcare",
      ),
    );
  });
});
