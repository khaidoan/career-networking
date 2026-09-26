import { useRef } from "react";
import { render, screen } from "@testing-library/react";
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
});
