/**
 * Company add/edit form state, its client-side checks (mirroring `schemas/companies.py`) and the
 * conversions to and from the companies API shapes. Form keys match the API field names, so the
 * server's 422 messages land on the same fields.
 */

import type { Company, CompanyWrite } from "@/lib/api/companies";
import type { FieldErrors } from "@/lib/api/request";

/** Server limits from `schemas/companies.py`. */
export const MAX_COMPANY_NAME_LENGTH = 200;
export const MAX_COMPANY_URL_LENGTH = 2000;
export const MAX_COMPANY_SHORT_TEXT_LENGTH = 100;
export const MAX_COMPANY_LONG_TEXT_LENGTH = 10_000;
export const MAX_COMPANY_INDUSTRIES = 20;

const LINKEDIN_HOST = "linkedin.com";

export type CompanyFormValues = {
  name: string;
  website_url: string;
  linkedin_url: string;
  logo_url: string;
  description: string;
  industries: string[];
  growth_stage: string;
  employee_estimate: string;
  history: string;
};

export function toCompanyFormValues(
  company: Company | null,
): CompanyFormValues {
  return {
    name: company?.name ?? "",
    website_url: company?.website_url ?? "",
    linkedin_url: company?.linkedin_url ?? "",
    logo_url: company?.logo_url ?? "",
    description: company?.description ?? "",
    industries: company?.industries ?? [],
    growth_stage: company?.growth_stage ?? "",
    employee_estimate: company?.employee_estimate ?? "",
    history: company?.history ?? "",
  };
}

/** The host of an absolute http(s) URL, or `null` when the text is not one. */
function httpHost(value: string): string | null {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") &&
      url.hostname
      ? url.hostname.toLowerCase()
      : null;
  } catch {
    return null;
  }
}

function checkText(
  errors: FieldErrors,
  key: keyof CompanyFormValues,
  value: string,
  { label, max, required }: { label: string; max: number; required: boolean },
) {
  const text = value.trim();
  if (!text) {
    if (required) {
      errors[key] = `Enter ${label}.`;
    }
    return;
  }
  if (text.length > max) {
    errors[key] = `Use ${max.toLocaleString("en-US")} characters or fewer.`;
  }
}

function checkUrl(
  errors: FieldErrors,
  key: keyof CompanyFormValues,
  value: string,
  { label, required }: { label: string; required: boolean },
) {
  checkText(errors, key, value, {
    label,
    max: MAX_COMPANY_URL_LENGTH,
    required,
  });
  const text = value.trim();
  if (!errors[key] && text && httpHost(text) === null) {
    errors[key] = "Enter a full URL starting with https:// or http://.";
  }
}

/**
 * Checks that mirror the server rules, so obvious mistakes are caught before a request. The
 * server still validates everything.
 */
export function validateCompany(values: CompanyFormValues): FieldErrors {
  const errors: FieldErrors = {};
  checkText(errors, "name", values.name, {
    label: "the company name",
    max: MAX_COMPANY_NAME_LENGTH,
    required: true,
  });
  checkUrl(errors, "website_url", values.website_url, {
    label: "the website URL",
    required: true,
  });
  checkUrl(errors, "linkedin_url", values.linkedin_url, {
    label: "the LinkedIn URL",
    required: true,
  });
  if (!errors.linkedin_url) {
    const host = httpHost(values.linkedin_url.trim()) ?? "";
    if (host !== LINKEDIN_HOST && !host.endsWith(`.${LINKEDIN_HOST}`)) {
      errors.linkedin_url = "Enter a linkedin.com URL.";
    }
  }
  checkUrl(errors, "logo_url", values.logo_url, {
    label: "the logo URL",
    required: false,
  });
  checkText(errors, "description", values.description, {
    label: "a description",
    max: MAX_COMPANY_LONG_TEXT_LENGTH,
    required: true,
  });
  if (values.industries.length === 0) {
    errors.industries = "Add at least one industry.";
  } else if (values.industries.length > MAX_COMPANY_INDUSTRIES) {
    errors.industries = `Add ${MAX_COMPANY_INDUSTRIES} industries or fewer.`;
  }
  checkText(errors, "growth_stage", values.growth_stage, {
    label: "the growth stage",
    max: MAX_COMPANY_SHORT_TEXT_LENGTH,
    required: true,
  });
  checkText(errors, "employee_estimate", values.employee_estimate, {
    label: "the employee estimate",
    max: MAX_COMPANY_SHORT_TEXT_LENGTH,
    required: true,
  });
  checkText(errors, "history", values.history, {
    label: "the history",
    max: MAX_COMPANY_LONG_TEXT_LENGTH,
    required: false,
  });
  return errors;
}

/** API body for create and update; call only after `validateCompany` returned no errors. */
export function toCompanyWrite(values: CompanyFormValues): CompanyWrite {
  return {
    name: values.name.trim(),
    website_url: values.website_url.trim(),
    linkedin_url: values.linkedin_url.trim(),
    logo_url: values.logo_url.trim() || null,
    description: values.description.trim(),
    industries: values.industries,
    growth_stage: values.growth_stage.trim(),
    employee_estimate: values.employee_estimate.trim(),
    history: values.history.trim() || null,
  };
}

/**
 * The LinkedIn people tab for a company page: the URL without its query, fragment or trailing
 * slash, then `/people/`. For example `.../company/acme/` -> `.../company/acme/people/`.
 */
export function linkedInPeopleUrl(linkedinUrl: string): string {
  try {
    const url = new URL(linkedinUrl.trim());
    url.search = "";
    url.hash = "";
    url.pathname = `${url.pathname.replace(/\/+$/, "")}/people/`;
    return url.toString();
  } catch {
    return `${linkedinUrl.trim().replace(/\/+$/, "")}/people/`;
  }
}

/** The message shown when a company still has jobs (same as the API's 409 `detail`). */
export const COMPANY_HAS_JOBS_MESSAGE = "Companies with jobs can't be deleted.";
