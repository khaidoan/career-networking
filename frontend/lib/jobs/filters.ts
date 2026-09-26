/**
 * Inbox filters in the page URL. Query parameter names match the API's (`seniority`,
 * `work_arrangement`, `job_type`, `visa`, `liked`, `company`), and unknown values are dropped.
 */

import type { JobFilters } from "@/lib/api/jobs";
import {
  JOB_TYPE_OPTIONS,
  SENIORITY_OPTIONS,
  WORK_ARRANGEMENT_OPTIONS,
  type Option,
} from "@/lib/profile/options";

type ReadableParams = Pick<URLSearchParams, "get" | "getAll">;

export type MultiFilterKey = "seniority" | "work_arrangement" | "job_type";

export const MULTI_FILTERS: readonly {
  key: MultiFilterKey;
  label: string;
  options: readonly Option[];
}[] = [
  { key: "seniority", label: "Seniority", options: SENIORITY_OPTIONS },
  {
    key: "work_arrangement",
    label: "Work arrangement",
    options: WORK_ARRANGEMENT_OPTIONS,
  },
  { key: "job_type", label: "Job type", options: JOB_TYPE_OPTIONS },
];

export const VISA_FILTER_OPTIONS: readonly Option[] = [
  { value: "yes", label: "Sponsors visas" },
  { value: "no", label: "No visa sponsorship" },
];

/** Changes that remove every inbox filter and the company search. */
export const CLEAR_JOB_FILTERS = {
  seniority: null,
  work_arrangement: null,
  job_type: null,
  visa: null,
  liked: null,
  company: null,
} as const;

function known(values: string[], options: readonly Option[]): string[] {
  const allowed = new Set(options.map((option) => option.value));
  return [...new Set(values)].filter((value) => allowed.has(value));
}

export function jobFiltersFromParams(params: ReadableParams): JobFilters {
  const visa = params.get("visa");
  return {
    seniority: known(params.getAll("seniority"), SENIORITY_OPTIONS),
    work_arrangement: known(
      params.getAll("work_arrangement"),
      WORK_ARRANGEMENT_OPTIONS,
    ),
    job_type: known(params.getAll("job_type"), JOB_TYPE_OPTIONS),
    visa: visa === "yes" || visa === "no" ? visa : null,
    liked: params.get("liked") === "true",
    company: params.get("company")?.trim() ?? "",
  };
}

/** How many filter controls are set (the company search is counted separately). */
export function activeFilterCount(filters: JobFilters): number {
  return (
    MULTI_FILTERS.filter(({ key }) => filters[key].length > 0).length +
    (filters.visa ? 1 : 0) +
    (filters.liked ? 1 : 0)
  );
}

export function hasActiveJobFilters(filters: JobFilters): boolean {
  return activeFilterCount(filters) > 0 || filters.company !== "";
}
