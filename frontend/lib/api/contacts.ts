/**
 * Browser-side calls to the networking contacts API: `/api/v1/contacts` and the company contact
 * search (`/api/v1/companies/{id}/contacts/search`).
 */

import {
  NETWORK_ERROR_MESSAGE,
  readDetail,
  request,
  requestJson,
  toFailure,
  type ApiFailure,
} from "@/lib/api/request";

const CONTACTS_API = "/api/v1/contacts";
const COMPANIES_API = "/api/v1/companies";

// Used only when a 502/503 answer has no readable `detail` (for example an nginx error page).
const SEARCH_UNAVAILABLE_MESSAGE =
  "Contact search needs a SerpApi key. See the README.";
const SEARCH_FAILED_MESSAGE =
  "Contact search failed: the search service could not be reached. Try again later.";

/** A `company_networking` row; `name` joins the first and last names (`null` when both are). */
export type Contact = {
  id: number;
  company_id: number;
  name: string | null;
  first_name: string | null;
  last_name: string | null;
  title: string | null;
  linkedin_url: string | null;
  connection_request_sent: boolean;
  /** ISO 8601 timestamp of the first time the request was marked as sent. */
  connection_request_sent_at: string | null;
};

export type ContactResult = { ok: true; contact: Contact } | ApiFailure;

/** Record that a connection request was sent; calling it again keeps the first timestamp. */
export async function markConnectionRequestSent(
  contactId: number,
): Promise<ContactResult> {
  const result = await requestJson<Contact>(
    `${CONTACTS_API}/${contactId}/connection-request`,
    { method: "POST" },
  );
  return result.ok ? { ok: true, contact: result.data } : result;
}

/** Why "Find contacts" cannot run: no SerpApi key, or no recommended or applied job. */
export type ContactSearchUnavailableReason = "no_api_key" | "no_eligible_job";

/** Whether "Find contacts" can run for a company; embedded in Job and Company Details. */
export type ContactSearchStatus = {
  available: boolean;
  /** `null` when `available` is true. `no_api_key` wins when both apply. */
  unavailable_reason: ContactSearchUnavailableReason | null;
  /** ISO 8601 timestamp of the last successful search; `null` before the first. */
  last_searched_at: string | null;
};

/** One finished contact search: counts, the company's full contact list and the new status. */
export type ContactSearchResult = {
  found: number;
  created: number;
  updated: number;
  /** Every contact at the company (not only the ones found), sorted by id. */
  contacts: Contact[];
  contact_search: ContactSearchStatus;
};

export type FindContactsResult =
  { ok: true; result: ContactSearchResult } | ApiFailure;

/**
 * Run one contact search for a company. `jobId` picks the role to search for; without it the
 * company's most recently discovered recommended or applied job is used. A 409 (not eligible),
 * 503 (no SerpApi key) or 502 (SerpApi or the AI model failed) resolves with the API's message.
 */
export async function findContacts(
  companyId: number,
  jobId?: number,
): Promise<FindContactsResult> {
  const query =
    jobId === undefined
      ? ""
      : `?${new URLSearchParams({ job_id: String(jobId) })}`;
  const response = await request(
    `${COMPANIES_API}/${companyId}/contacts/search${query}`,
    { method: "POST" },
  );
  if (!response) {
    return {
      ok: false,
      kind: "network",
      message: NETWORK_ERROR_MESSAGE,
      fieldErrors: {},
    };
  }
  if (response.ok) {
    return {
      ok: true,
      result: (await response.json()) as ContactSearchResult,
    };
  }
  // The shared helper hides 5xx details; these two are written for users.
  if (response.status === 502 || response.status === 503) {
    const detail = await readDetail(response);
    const fallback =
      response.status === 503
        ? SEARCH_UNAVAILABLE_MESSAGE
        : SEARCH_FAILED_MESSAGE;
    return {
      ok: false,
      kind: "unexpected",
      message: typeof detail === "string" && detail ? detail : fallback,
      fieldErrors: {},
    };
  }
  return toFailure(response);
}
