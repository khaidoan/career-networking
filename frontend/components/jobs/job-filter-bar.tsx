"use client";

import { useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

import { MultiSelectFilter } from "@/components/common/multi-select-filter";
import { SelectField } from "@/components/profile/select-field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  useDebouncedSearchParam,
  useUrlFilters,
  type FilterChanges,
} from "@/hooks/use-url-filters";
import type { JobFilters } from "@/lib/api/jobs";
import {
  activeFilterCount,
  CLEAR_JOB_FILTERS,
  hasActiveJobFilters,
  jobFiltersFromParams,
  MULTI_FILTERS,
  VISA_FILTER_OPTIONS,
} from "@/lib/jobs/filters";

type FilterControlsProps = {
  /** Keeps ids unique between the inline bar and the mobile sheet. */
  idPrefix: string;
  filters: JobFilters;
  onChange: (changes: FilterChanges) => void;
  className?: string;
};

function FilterControls({
  idPrefix,
  filters,
  onChange,
  className,
}: FilterControlsProps) {
  const likedId = `${idPrefix}-liked`;
  return (
    <div className={className}>
      {MULTI_FILTERS.map(({ key, label, options }) => (
        <MultiSelectFilter
          key={key}
          id={`${idPrefix}-${key}`}
          label={label}
          options={options}
          selected={filters[key]}
          onChange={(values) => onChange({ [key]: values })}
        />
      ))}
      <SelectField
        id={`${idPrefix}-visa`}
        label="Visa sponsorship"
        value={filters.visa ?? ""}
        onChange={(value) => onChange({ visa: value || null })}
        options={VISA_FILTER_OPTIONS}
        notSetLabel="Any"
      />
      <div className="flex min-h-11 items-center gap-3">
        <Checkbox
          id={likedId}
          checked={filters.liked}
          onCheckedChange={(checked) =>
            onChange({ liked: checked === true ? "true" : null })
          }
        />
        <Label htmlFor={likedId}>Only liked</Label>
      </div>
    </div>
  );
}

/**
 * Inbox filters and the company search, all stored in the URL. Filters sit inline from `md`
 * up and move into a sheet on small screens; the search box is always visible.
 */
export function JobFilterBar() {
  const { searchParams, setFilters } = useUrlFilters();
  const [search, setSearch] = useDebouncedSearchParam("company");
  const [sheetOpen, setSheetOpen] = useState(false);
  const filters = jobFiltersFromParams(searchParams);
  const count = activeFilterCount(filters);
  const canClear = hasActiveJobFilters(filters) || search !== "";

  function clearAll() {
    setSearch("");
    setFilters(CLEAR_JOB_FILTERS);
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-surface p-4 shadow-soft-sm">
      <div className="flex items-end gap-2">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Label htmlFor="job-company-search">Search by company</Label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="job-company-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Company name"
              autoComplete="off"
              className="pl-9"
            />
          </div>
        </div>
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" className="md:hidden">
              <SlidersHorizontal aria-hidden="true" />
              Filters
              {count > 0 && (
                <span>
                  ({count}
                  <span className="sr-only"> active</span>)
                </span>
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="overflow-y-auto">
            <SheetHeader className="border-b">
              <SheetTitle>Filters</SheetTitle>
              <SheetDescription>
                The list updates as you change a filter.
              </SheetDescription>
            </SheetHeader>
            <FilterControls
              idPrefix="sheet-filter"
              filters={filters}
              onChange={setFilters}
              className="flex flex-col gap-6 px-4"
            />
            <div className="mt-auto flex flex-col gap-2 border-t p-4">
              {canClear && (
                <Button variant="outline" onClick={clearAll}>
                  Clear filters
                </Button>
              )}
              <Button onClick={() => setSheetOpen(false)}>Show results</Button>
            </div>
          </SheetContent>
        </Sheet>
      </div>
      <FilterControls
        idPrefix="filter"
        filters={filters}
        onChange={setFilters}
        className="hidden items-end gap-4 md:grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
      />
      {canClear && (
        <Button
          variant="ghost"
          onClick={clearAll}
          className="hidden self-start md:inline-flex"
        >
          <X aria-hidden="true" />
          Clear filters
        </Button>
      )}
    </div>
  );
}
