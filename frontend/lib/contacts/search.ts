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
    "Contact search is only available for companies with a recommended or applied job.",
};

function plural(count: number, word: string): string {
  return `${count} ${count === 1 ? word : `${word}s`}`;
}

/**
 * What a search did, in the user's terms: new contacts, people already in the list, or nobody
 * matching on LinkedIn (the Google search found no profiles for the company and role).
 */
export function describeContactSearch(
  result: Pick<ContactSearchResult, "found" | "created" | "updated">,
): string {
  const updated =
    result.updated > 0 ? ` (${plural(result.updated, "contact")} updated)` : "";
  if (result.created > 0) {
    return `Found ${plural(result.created, "new contact")}${updated}.`;
  }
  if (result.found > 0) {
    return `No new contacts: everyone found is already in your list${updated}.`;
  }
  return "No matching people were found on LinkedIn for this company and role.";
}
