/** Text for the "Find contacts" button, its disabled explanations and its announcements. */

import type {
  ContactSearchResult,
  ContactSearchUnavailableReason,
} from "@/lib/api/contacts";

/** Shown next to the disabled button, and linked to it with `aria-describedby`. */
export const CONTACT_SEARCH_UNAVAILABLE_MESSAGES: Record<
  ContactSearchUnavailableReason,
  string
> = {
  no_api_key:
    "Contact search needs a SerpApi key. See Contact search in the README to set one up.",
  no_eligible_job:
    "Contact search is available for companies with a recommended or applied job.",
};

function plural(count: number, word: string): string {
  return `${count} ${count === 1 ? word : `${word}s`}`;
}

/** For example "Found 3 new contacts, updated 1." or "No new contacts found." */
export function describeContactSearch(
  result: Pick<ContactSearchResult, "created" | "updated">,
): string {
  const updated = result.updated > 0 ? `, updated ${result.updated}` : "";
  if (result.created === 0) {
    return `No new contacts found${updated}.`;
  }
  return `Found ${plural(result.created, "new contact")}${updated}.`;
}
