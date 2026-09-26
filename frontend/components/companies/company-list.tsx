"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Building2, Plus, Search, SearchX, X } from "lucide-react";

import { CompanyCard } from "@/components/companies/company-card";
import { CompanyForm } from "@/components/companies/company-form";
import { InfiniteListFooter } from "@/components/common/infinite-list-footer";
import {
  EmptyState,
  LoadError,
  LoadingCards,
} from "@/components/common/list-states";
import { MultiSelectFilter } from "@/components/common/multi-select-filter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useInfiniteList, type FetchPage } from "@/hooks/use-infinite-list";
import {
  useDebouncedSearchParam,
  useUrlFilters,
} from "@/hooks/use-url-filters";
import {
  listCompanies,
  listIndustries,
  type CompanyCard as CompanyCardData,
  type CompanyFilters,
} from "@/lib/api/companies";

// Same two warm design tokens as the inbox cards.
const CARD_BACKGROUNDS = ["bg-surface", "bg-surface-alt"] as const;

const CLEAR_COMPANY_FILTERS = { q: null, industry: null } as const;

function companyCount(count: number) {
  return `${count} ${count === 1 ? "company" : "companies"}`;
}

function filtersFromParams(
  params: Pick<URLSearchParams, "get" | "getAll">,
): CompanyFilters {
  return {
    q: params.get("q")?.trim() ?? "",
    industry: [...new Set(params.getAll("industry"))].filter(Boolean),
  };
}

/** Industry options from the API, plus any selected in the URL that are not in use anymore. */
function useIndustryOptions(selected: readonly string[], version: number) {
  const [industries, setIndustries] = useState<string[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    listIndustries(controller.signal)
      .then((result) => {
        if (result.ok) {
          setIndustries(result.industries);
        }
      })
      .catch(() => {
        // Aborted on unmount; the filter keeps its previous options.
      });
    return () => controller.abort();
  }, [version]);

  return useMemo(() => {
    const all = [
      ...industries,
      ...selected.filter((industry) => !industries.includes(industry)),
    ];
    return all.map((industry) => ({ value: industry, label: industry }));
  }, [industries, selected]);
}

/**
 * The Companies page body: name search, the industry filter and "Add company" above an
 * infinitely scrolling card list, liked first then alphabetical. Search, filtering and paging
 * happen on the server; the search text and industries live in the URL.
 */
export function CompanyList() {
  const { searchParams, setFilters } = useUrlFilters();
  const [search, setSearch] = useDebouncedSearchParam("q");
  const [adding, setAdding] = useState(false);
  // Bumped after a save so new industries show up in the filter.
  const [industriesVersion, setIndustriesVersion] = useState(0);
  const filters = filtersFromParams(searchParams);
  const filtered = filters.q !== "" || filters.industry.length > 0;
  const canClear = filtered || search !== "";
  const industryOptions = useIndustryOptions(
    filters.industry,
    industriesVersion,
  );

  const resetKey = new URLSearchParams([
    ["q", filters.q],
    ...filters.industry.map((industry) => ["industry", industry]),
  ]).toString();

  const fetchPage: FetchPage<CompanyCardData> = async (cursor, signal) => {
    const result = await listCompanies(filters, { cursor, signal });
    return result.ok
      ? {
          ok: true,
          items: result.page.items,
          nextCursor: result.page.next_cursor,
        }
      : result;
  };

  const list = useInfiniteList<CompanyCardData>({
    resetKey,
    fetchPage,
    describeLoaded: (count) => `${companyCount(count)} more loaded`,
    describeResults: (count, hasMore) =>
      count === 0
        ? "No companies match your search"
        : `Showing ${hasMore ? "the first " : ""}${companyCount(count)}`,
  });

  function clearAll() {
    setSearch("");
    setFilters(CLEAR_COMPANY_FILTERS);
  }

  const listRef = useRef<HTMLUListElement>(null);
  const addButtonRef = useRef<HTMLButtonElement>(null);

  function handleDeleted(companyId: number) {
    list.removeItem(companyId);
    // The deleted card took the focused button with it; land on the list (or "Add company"
    // when it is now empty) instead of the page body.
    requestAnimationFrame(() => {
      if (!document.activeElement || document.activeElement === document.body) {
        (listRef.current ?? addButtonRef.current)?.focus();
      }
    });
  }

  function handleEdited(company: CompanyCardData) {
    list.updateItem(company);
    setIndustriesVersion((version) => version + 1);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-xl border bg-surface p-4 shadow-soft-sm md:flex-row md:items-end">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Label htmlFor="company-search">Search by name</Label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="company-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Company name"
              autoComplete="off"
              className="pl-9"
            />
          </div>
        </div>
        <MultiSelectFilter
          id="company-industry"
          label="Industry"
          options={industryOptions}
          selected={filters.industry}
          onChange={(industry) => setFilters({ industry })}
          emptyMessage="No industries yet"
          className="md:w-64"
        />
        <div className="flex flex-col gap-2 sm:flex-row md:shrink-0">
          {canClear && (
            <Button variant="ghost" onClick={clearAll}>
              <X aria-hidden="true" />
              Clear
            </Button>
          )}
          <Button ref={addButtonRef} onClick={() => setAdding(true)}>
            <Plus aria-hidden="true" />
            Add company
          </Button>
        </div>
      </div>

      <CompanyForm
        open={adding}
        onOpenChange={setAdding}
        company={null}
        onSaved={() => {
          // Reload so the new company appears in its sorted place.
          setIndustriesVersion((version) => version + 1);
          list.retry();
        }}
      />

      {list.status === "loading" && <LoadingCards label="Loading companies…" />}

      {list.status === "error" && (
        <LoadError
          title="Could not load companies"
          message={list.error}
          onRetry={list.retry}
        />
      )}

      {list.status === "ready" &&
        list.items.length === 0 &&
        (filtered ? (
          <EmptyState
            icon={SearchX}
            title="No companies match your search"
            message="Try a different name or remove an industry filter."
          >
            <Button variant="outline" onClick={clearAll}>
              Clear search and filters
            </Button>
          </EmptyState>
        ) : (
          <EmptyState
            icon={Building2}
            title="No companies yet"
            message="Companies appear here as jobs are discovered. You can also add one yourself."
          />
        ))}

      {list.status === "ready" && list.items.length > 0 && (
        <>
          <ul
            ref={listRef}
            tabIndex={-1}
            aria-label="Companies"
            className="flex flex-col gap-4"
          >
            {list.items.map((company, index) => (
              <CompanyCard
                key={company.id}
                company={company}
                onChange={list.updateItem}
                onEdited={handleEdited}
                onDeleted={handleDeleted}
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
            noun="companies"
            listRef={listRef}
          />
        </>
      )}
    </div>
  );
}
