"use client";

import { useRef } from "react";
import { Inbox, SearchX } from "lucide-react";

import { InfiniteListFooter } from "@/components/common/infinite-list-footer";
import {
  EmptyState,
  LoadError,
  LoadingCards,
} from "@/components/common/list-states";
import { JobCard } from "@/components/jobs/job-card";
import { JobFilterBar } from "@/components/jobs/job-filter-bar";
import { Button } from "@/components/ui/button";
import { useInfiniteList, type FetchPage } from "@/hooks/use-infinite-list";
import { useUrlFilters } from "@/hooks/use-url-filters";
import {
  jobListQuery,
  listJobs,
  type InboxType,
  type JobCard as JobCardData,
} from "@/lib/api/jobs";
import {
  CLEAR_JOB_FILTERS,
  hasActiveJobFilters,
  jobFiltersFromParams,
} from "@/lib/jobs/filters";
import { INBOX_EMPTY_STATES, INBOX_LABELS } from "@/lib/jobs/inbox";

// Two warm design tokens; both keep body and muted text above 4.5:1 contrast.
const CARD_BACKGROUNDS = ["bg-surface", "bg-surface-alt"] as const;

function jobCount(count: number) {
  return `${count} ${count === 1 ? "job" : "jobs"}`;
}

/**
 * One inbox: the filter bar plus an infinitely scrolling card list, liked first then newest.
 * Filtering, search and paging happen on the server; the filters live in the URL.
 */
export function JobList({ inbox }: { inbox: InboxType }) {
  const { searchParams, setFilters } = useUrlFilters();
  const filters = jobFiltersFromParams(searchParams);
  const filtered = hasActiveJobFilters(filters);

  const query = jobListQuery(inbox, filters).toString();

  const fetchPage: FetchPage<JobCardData> = async (cursor, signal) => {
    const result = await listJobs(inbox, filters, { cursor, signal });
    return result.ok
      ? {
          ok: true,
          items: result.page.items,
          nextCursor: result.page.next_cursor,
        }
      : result;
  };

  const list = useInfiniteList<JobCardData>({
    resetKey: query,
    fetchPage,
    describeLoaded: (count) => `${jobCount(count)} more loaded`,
    describeResults: (count, hasMore) =>
      count === 0
        ? "No jobs match your filters"
        : `Showing ${hasMore ? "the first " : ""}${jobCount(count)}`,
  });

  const empty = INBOX_EMPTY_STATES[inbox];
  const listRef = useRef<HTMLUListElement>(null);

  return (
    <div className="flex flex-col gap-6">
      <JobFilterBar />

      {list.status === "loading" && <LoadingCards label="Loading jobs…" />}

      {list.status === "error" && (
        <LoadError
          title="Could not load jobs"
          message={list.error}
          onRetry={list.retry}
        />
      )}

      {list.status === "ready" &&
        list.items.length === 0 &&
        (filtered ? (
          <EmptyState
            icon={SearchX}
            title="No jobs match your filters"
            message="Try removing a filter or searching for a different company."
          >
            <Button
              variant="outline"
              onClick={() => setFilters(CLEAR_JOB_FILTERS)}
            >
              Clear filters
            </Button>
          </EmptyState>
        ) : (
          <EmptyState
            icon={Inbox}
            title={empty.title}
            message={empty.message}
          />
        ))}

      {list.status === "ready" && list.items.length > 0 && (
        <>
          <ul
            ref={listRef}
            aria-label={`${INBOX_LABELS[inbox]} jobs`}
            className="flex flex-col gap-4"
          >
            {list.items.map((job, index) => (
              <JobCard
                key={job.id}
                job={job}
                onChange={list.updateItem}
                className={CARD_BACKGROUNDS[index % CARD_BACKGROUNDS.length]}
              />
            ))}
          </ul>
          <InfiniteListFooter
            hasMore={list.hasMore}
            loadingMore={list.loadingMore}
            error={list.loadMoreError}
            onLoadMore={list.loadMore}
            sentinelRef={list.sentinelRef}
            noun="jobs"
            listRef={listRef}
          />
        </>
      )}
    </div>
  );
}
