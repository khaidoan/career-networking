/** Browser-side calls to the jobs API (`/api/v1/jobs`): inboxes, Job Details and job actions. */

import type { Company } from "@/lib/api/companies";
import type { Contact } from "@/lib/api/contacts";
import {
  jsonBody,
  requestJson,
  type ApiFailure,
  type ApiResult,
} from "@/lib/api/request";

const JOBS_API = "/api/v1/jobs";

/** Stored inbox slugs (the Need Attention route is `/inbox/need-attention`). */
export type InboxType =
  "recommended" | "applied" | "ignored" | "need_attention";

/** One job in an inbox list, with the few company fields a card shows. */
export type JobCard = {
  id: number;
  title: string;
  company_id: number;
  company_name: string;
  company_industries: string[];
  company_growth_stage: string | null;
  location_city: string | null;
  location_state: string | null;
  /** ISO 3166-1 alpha-2 code, for example "US". */
  location_country: string | null;
  work_arrangement: string | null;
  job_type_classification: string | null;
  seniority_level: string | null;
  year_exp: number | null;
  compensation_range: string | null;
  visa_sponsorship: boolean | null;
  overall_score: number | null;
  /** Why the last evaluation failed; the scores are `null` while this is set. */
  evaluation_error: string | null;
  inbox_type: InboxType;
  liked: boolean;
  /** ISO 8601 timestamps. */
  discovered_when: string;
  applied_when: string | null;
};

/** One job with its full text, all four scores, its company and the company's contacts. */
export type JobDetail = JobCard & {
  url: string;
  source: string | null;
  description: string | null;
  experience_score: number | null;
  skill_score: number | null;
  industry_exp_score: number | null;
  company: Company;
  contacts: Contact[];
};

/** Inbox filters, named after their query parameters (empty values are not sent). */
export type JobFilters = {
  seniority: string[];
  work_arrangement: string[];
  job_type: string[];
  visa: "yes" | "no" | null;
  liked: boolean;
  /** Company name search text (typo-tolerant on the server). */
  company: string;
};

export type JobPage = {
  items: JobCard[];
  /** Opaque cursor for the next page; `null` on the last page. */
  next_cursor: string | null;
};

export type JobPageResult = { ok: true; page: JobPage } | ApiFailure;
export type JobResult = { ok: true; job: JobDetail } | ApiFailure;

type RequestOptions = { cursor?: string | null; signal?: AbortSignal };

function jobResult(result: ApiResult<JobDetail>): JobResult {
  return result.ok ? { ok: true, job: result.data } : result;
}

/** The API query string for an inbox page. */
export function jobListQuery(
  inbox: InboxType,
  filters: JobFilters,
  cursor?: string | null,
): URLSearchParams {
  const query = new URLSearchParams({ inbox });
  for (const key of ["seniority", "work_arrangement", "job_type"] as const) {
    for (const value of filters[key]) {
      query.append(key, value);
    }
  }
  if (filters.visa) {
    query.set("visa", filters.visa);
  }
  if (filters.liked) {
    query.set("liked", "true");
  }
  if (filters.company.trim()) {
    query.set("company", filters.company.trim());
  }
  if (cursor) {
    query.set("cursor", cursor);
  }
  return query;
}

/** One page of an inbox, liked first then newest. */
export async function listJobs(
  inbox: InboxType,
  filters: JobFilters,
  { cursor, signal }: RequestOptions = {},
): Promise<JobPageResult> {
  const query = jobListQuery(inbox, filters, cursor);
  const result = await requestJson<JobPage>(`${JOBS_API}?${query}`, {
    signal,
  });
  return result.ok ? { ok: true, page: result.data } : result;
}

export async function getJob(
  jobId: number,
  signal?: AbortSignal,
): Promise<JobResult> {
  return jobResult(
    await requestJson<JobDetail>(`${JOBS_API}/${jobId}`, { signal }),
  );
}

export async function setJobLiked(
  jobId: number,
  liked: boolean,
): Promise<JobResult> {
  return jobResult(
    await requestJson<JobDetail>(
      `${JOBS_API}/${jobId}`,
      jsonBody("PATCH", { liked }),
    ),
  );
}

/** Move the job to Applied; calling it again keeps the first `applied_when`. */
export async function applyToJob(jobId: number): Promise<JobResult> {
  return jobResult(
    await requestJson<JobDetail>(`${JOBS_API}/${jobId}/apply`, {
      method: "POST",
    }),
  );
}

/**
 * Evaluate the job again against the current preferences. A failed evaluation still succeeds
 * here: the returned job then has `evaluation_error` set and no scores.
 */
export async function reEvaluateJob(jobId: number): Promise<JobResult> {
  return jobResult(
    await requestJson<JobDetail>(`${JOBS_API}/${jobId}/re-evaluate`, {
      method: "POST",
    }),
  );
}
