"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAnnounce } from "@/components/ui/announcer";
import { UNEXPECTED_ERROR_MESSAGE, type ApiFailure } from "@/lib/api/request";

export type PageResult<T> =
  { ok: true; items: T[]; nextCursor: string | null } | ApiFailure;

/** Loads one page; `cursor` is `null` for the first page. */
export type FetchPage<T> = (
  cursor: string | null,
  signal: AbortSignal,
) => Promise<PageResult<T>>;

type UseInfiniteListOptions<T> = {
  /** Changing the key drops the loaded rows and loads the first page again (e.g. new filters). */
  resetKey: string;
  fetchPage: FetchPage<T>;
  /** The announcement after more rows load, e.g. `(count) => \`${count} more jobs loaded\``. */
  describeLoaded: (count: number) => string;
  /** The announcement when the first page reloads after a reset, e.g. "12 jobs shown". */
  describeResults: (count: number, hasMore: boolean) => string;
};

type ListState<T> = {
  key: string;
  attempt: number;
  items: T[];
  nextCursor: string | null;
  error: string | null;
  more: "idle" | "loading" | "error";
  moreError: string | null;
};

// Start loading the next page a little before the sentinel scrolls into view.
const SENTINEL_ROOT_MARGIN = "400px 0px";

function emptyPage<T>(): Omit<ListState<T>, "key" | "attempt"> {
  return {
    items: [],
    nextCursor: null,
    error: null,
    more: "idle",
    moreError: null,
  };
}

function appendUnique<T extends { id: number }>(items: T[], more: T[]): T[] {
  // A row can move pages when it is liked or unliked between loads; keep its first copy.
  const seen = new Set(items.map((item) => item.id));
  return [...items, ...more.filter((item) => !seen.has(item.id))];
}

/**
 * Cursor-paged list state for infinite scroll: loads the first page whenever `resetKey` changes,
 * loads the next page when the sentinel nears the viewport or `loadMore` is called (the
 * focusable "Load more" fallback), and announces newly loaded rows.
 */
export function useInfiniteList<T extends { id: number }>({
  resetKey,
  fetchPage,
  describeLoaded,
  describeResults,
}: UseInfiniteListOptions<T>) {
  const announce = useAnnounce();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ListState<T> | null>(null);
  const [sentinel, setSentinel] = useState<Element | null>(null);
  const fetchRef = useRef(fetchPage);
  const describeRef = useRef({ describeLoaded, describeResults });
  const moreController = useRef<AbortController | null>(null);
  const hasLoaded = useRef(false);

  const current =
    state && state.key === resetKey && state.attempt === attempt ? state : null;
  const currentRef = useRef(current);

  useEffect(() => {
    fetchRef.current = fetchPage;
    describeRef.current = { describeLoaded, describeResults };
    currentRef.current = current;
  });

  useEffect(() => {
    const controller = new AbortController();
    moreController.current?.abort();
    moreController.current = null;

    function finish(next: Omit<ListState<T>, "key" | "attempt">) {
      setState({ key: resetKey, attempt, ...next });
    }

    fetchRef.current(null, controller.signal).then(
      (result) => {
        if (controller.signal.aborted) {
          return;
        }
        if (!result.ok) {
          finish({ ...emptyPage<T>(), error: result.message });
          return;
        }
        finish({
          ...emptyPage<T>(),
          items: result.items,
          nextCursor: result.nextCursor,
        });
        if (hasLoaded.current) {
          announce(
            describeRef.current.describeResults(
              result.items.length,
              result.nextCursor !== null,
            ),
          );
        }
        hasLoaded.current = true;
      },
      () => {
        if (!controller.signal.aborted) {
          finish({ ...emptyPage<T>(), error: UNEXPECTED_ERROR_MESSAGE });
        }
      },
    );
    return () => controller.abort();
  }, [resetKey, attempt, announce]);

  const loadMore = useCallback(async () => {
    const snapshot = currentRef.current;
    if (
      !snapshot ||
      snapshot.error ||
      !snapshot.nextCursor ||
      moreController.current
    ) {
      return;
    }
    const controller = new AbortController();
    moreController.current = controller;
    const isSameList = (list: ListState<T> | null): list is ListState<T> =>
      list !== null &&
      list.key === snapshot.key &&
      list.attempt === snapshot.attempt;
    const update = (change: (list: ListState<T>) => ListState<T>) =>
      setState((list) => (isSameList(list) ? change(list) : list));

    update((list) => ({ ...list, more: "loading", moreError: null }));
    let result: PageResult<T>;
    try {
      result = await fetchRef.current(snapshot.nextCursor, controller.signal);
    } catch {
      result = {
        ok: false,
        kind: "unexpected",
        message: UNEXPECTED_ERROR_MESSAGE,
        fieldErrors: {},
      };
    }
    if (controller.signal.aborted) {
      return;
    }
    moreController.current = null;
    if (result.ok) {
      const { items, nextCursor } = result;
      update((list) => ({
        ...list,
        items: appendUnique(list.items, items),
        nextCursor,
        more: "idle",
      }));
      announce(describeRef.current.describeLoaded(items.length));
    } else {
      const message = result.message;
      update((list) => ({ ...list, more: "error", moreError: message }));
      announce(message, "error");
    }
  }, [announce]);

  const itemCount = current?.items.length ?? 0;
  const autoLoad = current?.more === "idle" && current.nextCursor !== null;

  useEffect(() => {
    if (!sentinel || !autoLoad || typeof IntersectionObserver === "undefined") {
      return;
    }
    // Re-created after each page, so a sentinel that is still visible loads the next one too.
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void loadMore();
        }
      },
      { rootMargin: SENTINEL_ROOT_MARGIN },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [sentinel, autoLoad, itemCount, loadMore]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  /** Replace one loaded row in place (e.g. after a like or a re-evaluation). */
  const updateItem = useCallback((item: T) => {
    setState(
      (list) =>
        list && {
          ...list,
          items: list.items.map((existing) =>
            existing.id === item.id ? item : existing,
          ),
        },
    );
  }, []);

  /** Drop one loaded row (e.g. after it was deleted). */
  const removeItem = useCallback((id: number) => {
    setState(
      (list) =>
        list && {
          ...list,
          items: list.items.filter((existing) => existing.id !== id),
        },
    );
  }, []);

  return {
    items: current?.items ?? [],
    status: !current ? "loading" : current.error ? "error" : "ready",
    error: current?.error ?? null,
    hasMore: Boolean(current && !current.error && current.nextCursor),
    loadingMore: current?.more === "loading",
    loadMoreError: current?.moreError ?? null,
    loadMore,
    retry,
    updateItem,
    removeItem,
    /** Attach to an element after the last row; it triggers loading as it nears the viewport. */
    sentinelRef: setSentinel,
  } as const;
}
