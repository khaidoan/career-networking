"use client";

import { useEffect, useRef } from "react";
import { LoaderCircle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";

type InfiniteListFooterProps = {
  hasMore: boolean;
  loadingMore: boolean;
  error: string | null;
  onLoadMore: () => void;
  sentinelRef: (element: Element | null) => void;
  /** Plural noun for the button, e.g. "jobs". */
  noun: string;
  /**
   * The list the rows are added to. When "Load more" fetches the last page the button goes
   * away, so focus moves to the first newly loaded row instead of dropping to the page body.
   */
  listRef?: React.RefObject<HTMLElement | null>;
};

/**
 * End of an infinite-scroll list: the invisible scroll sentinel plus a focusable "Load more"
 * button for keyboard and screen reader users, and the error with a retry.
 */
export function InfiniteListFooter({
  hasMore,
  loadingMore,
  error,
  onLoadMore,
  sentinelRef,
  noun,
  listRef,
}: InfiniteListFooterProps) {
  // Row count when the button was activated; set only while a button-triggered load runs.
  const loadStartedAt = useRef<number | null>(null);

  useEffect(() => {
    const from = loadStartedAt.current;
    if (from === null || loadingMore) {
      return;
    }
    loadStartedAt.current = null;
    if (document.activeElement && document.activeElement !== document.body) {
      return;
    }
    const firstNew = listRef?.current?.children[from];
    firstNew?.querySelector<HTMLElement>("a[href], button")?.focus();
  }, [hasMore, loadingMore, listRef]);

  if (!hasMore) {
    return null;
  }
  return (
    <div className="flex flex-col items-center gap-2 pt-2">
      <div ref={sentinelRef} aria-hidden="true" className="h-px w-full" />
      {error && <p className="text-sm font-medium text-destructive">{error}</p>}
      <Button
        type="button"
        variant="outline"
        aria-disabled={loadingMore || undefined}
        onClick={() => {
          if (!loadingMore) {
            loadStartedAt.current = listRef?.current?.children.length ?? null;
            onLoadMore();
          }
        }}
      >
        {loadingMore ? (
          <>
            <LoaderCircle aria-hidden="true" className="animate-spin" />
            Loading more {noun}…
          </>
        ) : error ? (
          <>
            <RotateCw aria-hidden="true" />
            Try again
          </>
        ) : (
          `Load more ${noun}`
        )}
      </Button>
    </div>
  );
}
