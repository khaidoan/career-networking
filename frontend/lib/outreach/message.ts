/** The LinkedIn connection request note copied by click-to-connect. */

/** The approved template, word for word. Each `{...}` token is replaced by the bare value. */
export const CONNECTION_MESSAGE_TEMPLATE =
  "Hello {first_name}, I came across a job posting for {job_title} at your current company, {company_name}. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!";

export type ConnectionMessageValues = {
  /** The contact's first name. */
  firstName: string;
  jobTitle: string;
  companyName: string;
};

const PLACEHOLDER = /\{(first_name|job_title|company_name)\}/g;

/**
 * Fill the template with the trimmed values (no quotes or parentheses added). Nothing is ever
 * shortened, even when the result is longer than LinkedIn's 300-character note limit.
 */
export function buildConnectionMessage({
  firstName,
  jobTitle,
  companyName,
}: ConnectionMessageValues): string {
  const values: Record<string, string> = {
    first_name: firstName.trim(),
    job_title: jobTitle.trim(),
    company_name: companyName.trim(),
  };
  // One pass with a callback, so `$&`-style patterns or tokens inside a value are kept as typed.
  return CONNECTION_MESSAGE_TEMPLATE.replace(
    PLACEHOLDER,
    (_token, key: string) => values[key],
  );
}
