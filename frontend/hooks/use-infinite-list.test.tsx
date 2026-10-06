import { useRef } from "react";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InfiniteListFooter } from "@/components/common/infinite-list-footer";
import { AnnouncerProvider } from "@/components/ui/announcer";

import { useInfiniteList, type FetchPage } from "./use-infinite-list";

type Row = { id: number; name: string };

function RowList({ fetchPage }: { fetchPage: FetchPage<Row> }) {
  const list = useInfiniteList({
    resetKey: "all",
    fetchPage,
    describeLoaded: (count) => `Loaded ${count} more`,
    describeResults: (count) => `${count} rows shown`,
  });
  const listRef = useRef<HTMLUListElement>(null);
  return (
    <>
      <ul ref={listRef} aria-label="Rows">
        {list.items.map((row) => (
          <li key={row.id}>
            <a href={`/rows/${row.id}`}>{row.name}</a>
          </li>
        ))}
      </ul>
      <InfiniteListFooter
        hasMore={list.hasMore}
        caughtUp={list.caughtUp}
        caughtUpMessage="All caught up."
        loadingMore={list.loadingMore}
        error={list.loadMoreError}
        onLoadMore={list.loadMore}
        sentinelRef={list.sentinelRef}
        noun="rows"
        listRef={listRef}
      />
    </>
  );
}

describe("useInfiniteList", () => {
  it("loads the next page from the Load more button and announces it", async () => {
    const fetchPage = vi.fn<FetchPage<Row>>(async (cursor) =>
      cursor === null
        ? { ok: true, items: [{ id: 1, name: "First" }], nextCursor: "page-2" }
        : { ok: true, items: [{ id: 2, name: "Second" }], nextCursor: null },
    );
    const user = userEvent.setup();
    render(
      <AnnouncerProvider>
        <RowList fetchPage={fetchPage} />
      </AnnouncerProvider>,
    );

    expect(await screen.findByText("First")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more rows" }));

    expect(await screen.findByText("Second")).toBeInTheDocument();
    expect(fetchPage).toHaveBeenLastCalledWith("page-2", expect.anything());
    expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent(
      "Loaded 1 more",
    );
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("moves focus to the first new row when Load more fetches the last page", async () => {
    const fetchPage = vi.fn<FetchPage<Row>>(async (cursor) =>
      cursor === null
        ? { ok: true, items: [{ id: 1, name: "First" }], nextCursor: "page-2" }
        : {
            ok: true,
            items: [
              { id: 2, name: "Second" },
              { id: 3, name: "Third" },
            ],
            nextCursor: null,
          },
    );
    const user = userEvent.setup();
    render(
      <AnnouncerProvider>
        <RowList fetchPage={fetchPage} />
      </AnnouncerProvider>,
    );

    await screen.findByText("First");
    const loadMore = screen.getByRole("button", { name: "Load more rows" });
    loadMore.focus();
    await user.keyboard("{Enter}");

    // The button is gone with the last page, so focus lands on the first new row.
    await vi.waitFor(() =>
      expect(screen.getByRole("link", { name: "Second" })).toHaveFocus(),
    );
  });

  it("pauses when a feed is caught up and checks again when the end scrolls back into view", async () => {
    // jsdom has no IntersectionObserver; this one reports what the test says is visible.
    const observers = new Set<FakeObserver>();
    class FakeObserver {
      constructor(private callback: IntersectionObserverCallback) {}
      observe() {
        observers.add(this);
      }
      disconnect() {
        observers.delete(this);
      }
      report(visible: boolean) {
        this.callback(
          [{ isIntersecting: visible } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        );
      }
    }
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    const setEndVisible = (visible: boolean) =>
      act(() => [...observers].forEach((observer) => observer.report(visible)));

    const fetchPage = vi.fn<FetchPage<Row>>(async (cursor) => {
      if (cursor === null) {
        return { ok: true, items: [{ id: 1, name: "First" }], nextCursor: "a" };
      }
      if (cursor === "a") {
        return { ok: true, items: [], nextCursor: "b" };
      }
      return {
        ok: true,
        items: [{ id: 3, name: "Scored later" }],
        nextCursor: "c",
      };
    });
    render(
      <AnnouncerProvider>
        <RowList fetchPage={fetchPage} />
      </AnnouncerProvider>,
    );
    await screen.findByText("First");

    // Reaching the end loads the next page, which is empty: caught up.
    setEndVisible(true);
    expect(await screen.findByText("All caught up.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Check for new rows" }),
    ).toBeInTheDocument();

    // Staying at the end does not ask again...
    setEndVisible(true);
    setEndVisible(true);
    expect(fetchPage).toHaveBeenCalledTimes(2);

    // ...scrolling away and back does.
    setEndVisible(false);
    setEndVisible(true);
    expect(await screen.findByText("Scored later")).toBeInTheDocument();
    expect(fetchPage).toHaveBeenLastCalledWith("b", expect.anything());
    expect(screen.queryByText("All caught up.")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
