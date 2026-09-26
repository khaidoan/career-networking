/** Browser-side calls to the companies API (`/api/v1/companies`). */

import type { Contact, ContactSearchStatus } from "@/lib/api/contacts";
import type { JobCard } from "@/lib/api/jobs";
import {
  jsonBody,
  requestJson,
  type ApiFailure,
  type ApiResult,
} from "@/lib/api/request";

const COMPANIES_API = "/api/v1/companies";

/** A company in the Companies list. */
export type CompanyCard = {
  id: number;
  name: string;
  logo_url: string | null;
  industries: string[];
  growth_stage: string | null;
  employee_estimate: string | null;
  liked: boolean;
};

/** Every stored company field (embedded in Job Details). */
export type Company = CompanyCard & {
  website_url: string | null;
  linkedin_url: string | null;
  description: string | null;
  history: string | null;
};

/** Company Details: the company, its jobs (newest first), its contacts and search status. */
export type CompanyDetail = Company & {
  job_count: number;
  jobs: JobCard[];
  contacts: Contact[];
  contact_search: ContactSearchStatus;
};

/** The body of create and update; `PUT` replaces every field. */
export type CompanyWrite = {
  name: string;
  website_url: string;
  linkedin_url: string;
  logo_url: string | null;
  description: string;
  industries: string[];
  growth_stage: string;
  employee_estimate: string;
  history: string | null;
};

export type CompanyFilters = {
  /** Name search text (typo-tolerant on the server). */
  q: string;
  /** Matches companies in any of these industries. */
  industry: string[];
};

export type CompanyPage = {
  items: CompanyCard[];
  /** Opaque cursor for the next page; `null` on the last page. */
  next_cursor: string | null;
};

export type CompanyPageResult = { ok: true; page: CompanyPage } | ApiFailure;
export type CompanyResult = { ok: true; company: CompanyDetail } | ApiFailure;
export type IndustriesResult = { ok: true; industries: string[] } | ApiFailure;
export type DeleteCompanyResult = { ok: true } | ApiFailure;

type RequestOptions = { cursor?: string | null; signal?: AbortSignal };

function companyResult(result: ApiResult<CompanyDetail>): CompanyResult {
  return result.ok ? { ok: true, company: result.data } : result;
}

export async function listCompanies(
  filters: CompanyFilters,
  { cursor, signal }: RequestOptions = {},
): Promise<CompanyPageResult> {
  const query = new URLSearchParams();
  if (filters.q.trim()) {
    query.set("q", filters.q.trim());
  }
  for (const industry of filters.industry) {
    query.append("industry", industry);
  }
  if (cursor) {
    query.set("cursor", cursor);
  }
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  const result = await requestJson<CompanyPage>(`${COMPANIES_API}${suffix}`, {
    signal,
  });
  return result.ok ? { ok: true, page: result.data } : result;
}

/** Every distinct industry across companies, sorted. */
export async function listIndustries(
  signal?: AbortSignal,
): Promise<IndustriesResult> {
  const result = await requestJson<string[]>(`${COMPANIES_API}/industries`, {
    signal,
  });
  return result.ok ? { ok: true, industries: result.data } : result;
}

export async function getCompany(
  companyId: number,
  signal?: AbortSignal,
): Promise<CompanyResult> {
  return companyResult(
    await requestJson<CompanyDetail>(`${COMPANIES_API}/${companyId}`, {
      signal,
    }),
  );
}

/** Add a company; a 422 failure carries per-field messages in `fieldErrors`. */
export async function createCompany(
  company: CompanyWrite,
): Promise<CompanyResult> {
  return companyResult(
    await requestJson<CompanyDetail>(COMPANIES_API, jsonBody("POST", company)),
  );
}

/** Replace every editable field; a 422 failure carries per-field messages in `fieldErrors`. */
export async function updateCompany(
  companyId: number,
  company: CompanyWrite,
): Promise<CompanyResult> {
  return companyResult(
    await requestJson<CompanyDetail>(
      `${COMPANIES_API}/${companyId}`,
      jsonBody("PUT", company),
    ),
  );
}

export async function setCompanyLiked(
  companyId: number,
  liked: boolean,
): Promise<CompanyResult> {
  return companyResult(
    await requestJson<CompanyDetail>(
      `${COMPANIES_API}/${companyId}`,
      jsonBody("PATCH", { liked }),
    ),
  );
}

/** Delete a company and its contacts; fails with `kind: "conflict"` while it still has jobs. */
export async function deleteCompany(
  companyId: number,
): Promise<DeleteCompanyResult> {
  const result = await requestJson<undefined>(`${COMPANIES_API}/${companyId}`, {
    method: "DELETE",
  });
  return result.ok ? { ok: true } : result;
}
