/** Browser-side calls to the networking contacts API (`/api/v1/contacts`). */

import { requestJson, type ApiFailure } from "@/lib/api/request";

const CONTACTS_API = "/api/v1/contacts";

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
