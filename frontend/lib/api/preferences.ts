/**
 * Browser-side calls to the same-origin preferences API (`/api/v1/preferences`, proxied to the
 * jobs service). Follows `lib/auth/client.ts`: the session cookie is sent with
 * `credentials: "include"` and every call resolves to a typed result instead of throwing.
 */

import type { EeoQuestionKey } from "@/lib/profile/options";
import {
  failureMessage,
  fieldErrorsFromDetail,
  INVALID_INPUT_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  readDetail,
  request,
  SESSION_EXPIRED_MESSAGE,
  UNEXPECTED_ERROR_MESSAGE,
  type Failure,
  type FieldErrors,
} from "@/lib/api/request";

const PREFERENCES_API = "/api/v1/preferences";

export {
  fieldErrorsFromDetail,
  NETWORK_ERROR_MESSAGE,
  SESSION_EXPIRED_MESSAGE,
  UNEXPECTED_ERROR_MESSAGE,
};
export type { Failure, FieldErrors };
export const INVALID_PREFERENCES_MESSAGE = INVALID_INPUT_MESSAGE;
export const RESUME_TOO_LARGE_MESSAGE =
  "The resume is larger than 10 MB. Upload a smaller file.";
export const RESUME_WRONG_TYPE_MESSAGE =
  "Only PDF (.pdf) and Word (.docx) resumes are supported.";

export type ResumeFileType = "pdf" | "docx";

export type ResumeInfo = {
  file_type: ResumeFileType;
  /** Name of the uploaded file, as chosen by the user. */
  file_name: string;
  /** ISO 8601 timestamp of the last upload. */
  uploaded_at: string;
};

export type EeoAnswers = Partial<Record<EeoQuestionKey, string | null>>;

/** Every editable preference; `PUT` replaces all of them at once. */
export type PreferencesUpdate = {
  desired_titles: string[];
  /** Titles containing every word of one of these are skipped by the job fetcher. */
  excluded_title_words: string[];
  hard_skills: string[];
  soft_skills: string[];
  country: string | null;
  currency: string | null;
  salary_min: number | null;
  salary_max: number | null;
  seniority: string[];
  address: string | null;
  gender: string | null;
  /** `null` until answered. */
  willing_to_relocate: boolean | null;
  /** States or cities ("Texas", "Austin, TX") the user will not relocate to. */
  excluded_relocation_places: string[];
  /** Applied by the fetcher only when `willing_to_relocate` is `false`. */
  max_commute_miles: number | null;
  eeo_answers: EeoAnswers;
  /**
   * Free text from the "Other" section: a long-form resume plus application facts, used to fill
   * in application forms and to write the resume and cover letter.
   */
  additional_information: string | null;
  /** Whether jobs may be applied to automatically; off by default. */
  auto_apply: boolean;
  /** Daily fetcher time as "HH:MM" in `fetch_timezone`; required on every save. */
  fetch_time: string;
  /** IANA time zone name; required on every save. */
  fetch_timezone: string;
};

/** A value job fetching needs before it is enabled. */
export type FetchingRequirement =
  "desired_titles" | "country" | "fetch_time" | "fetch_timezone";

export type JobFetchingStatus = {
  enabled: boolean;
  /** Empty when enabled. */
  missing: FetchingRequirement[];
  /** ISO 8601 time of the next daily run; `null` while disabled. */
  next_run_at: string | null;
};

export type Preferences = Omit<
  PreferencesUpdate,
  "fetch_time" | "fetch_timezone"
> & {
  /** `null` until saved; job fetching stays disabled until both are set. */
  fetch_time: string | null;
  fetch_timezone: string | null;
  resume: ResumeInfo | null;
  job_fetching: JobFetchingStatus;
  relocation_check: RelocationCheck;
};

/** How the server reads the saved address and relocation places. */
export type RelocationCheck = {
  /** The home city found in the address ("Austin, Texas"), or `null`. */
  home: string | null;
  /** Saved places that name no known state or city, so the fetcher ignores them. */
  unrecognized_places: string[];
};

export type ResumeSuggestions = {
  desired_titles: string[];
  hard_skills: string[];
  soft_skills: string[];
  seniority: string[];
  /** ISO 3166-1 alpha-2 code, or `null` when the resume does not make it clear. */
  country: string | null;
  /** One line, or `null` when the resume has none. */
  address: string | null;
};

export type ResumeUpload = {
  resume: ResumeInfo;
  /**
   * Already added to the saved preferences. `null` when the model could not produce
   * suggestions; `warning` then says why.
   */
  suggestions: ResumeSuggestions | null;
  warning: string | null;
  /** Everything saved after the upload, suggestions included. */
  preferences: Preferences;
};

export type PreferencesResult =
  { ok: true; preferences: Preferences } | Failure;
export type SaveResult =
  | { ok: true; preferences: Preferences }
  | (Failure & { fieldErrors: FieldErrors });
export type UploadResult = ({ ok: true } & ResumeUpload) | Failure;
export type DeleteResult = { ok: true } | Failure;

export async function getPreferences(
  signal?: AbortSignal,
): Promise<PreferencesResult> {
  const response = await request(PREFERENCES_API, { signal });
  if (!response) {
    return { ok: false, message: NETWORK_ERROR_MESSAGE };
  }
  if (response.ok) {
    return { ok: true, preferences: (await response.json()) as Preferences };
  }
  return { ok: false, message: failureMessage(response, undefined) };
}

export async function savePreferences(
  update: PreferencesUpdate,
): Promise<SaveResult> {
  const response = await request(PREFERENCES_API, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!response) {
    return { ok: false, message: NETWORK_ERROR_MESSAGE, fieldErrors: {} };
  }
  if (response.ok) {
    return { ok: true, preferences: (await response.json()) as Preferences };
  }
  const detail = await readDetail(response);
  if (response.status === 422) {
    const fieldErrors = fieldErrorsFromDetail(detail);
    return {
      ok: false,
      message:
        Object.keys(fieldErrors).length > 0
          ? INVALID_PREFERENCES_MESSAGE
          : failureMessage(response, detail),
      fieldErrors,
    };
  }
  return {
    ok: false,
    message: failureMessage(response, detail),
    fieldErrors: {},
  };
}

export async function uploadResume(file: File): Promise<UploadResult> {
  const body = new FormData();
  body.append("file", file);
  const response = await request(`${PREFERENCES_API}/resume`, {
    method: "POST",
    body,
  });
  if (!response) {
    return { ok: false, message: NETWORK_ERROR_MESSAGE };
  }
  if (response.ok) {
    const upload = (await response.json()) as ResumeUpload;
    return { ok: true, ...upload, warning: upload.warning ?? null };
  }
  const detail = await readDetail(response);
  // nginx answers oversized bodies itself with an HTML page, so 413 needs its own message.
  if (response.status === 413 && typeof detail !== "string") {
    return { ok: false, message: RESUME_TOO_LARGE_MESSAGE };
  }
  return { ok: false, message: failureMessage(response, detail) };
}

export async function deleteResume(): Promise<DeleteResult> {
  const response = await request(`${PREFERENCES_API}/resume`, {
    method: "DELETE",
  });
  if (!response) {
    return { ok: false, message: NETWORK_ERROR_MESSAGE };
  }
  if (response.ok) {
    return { ok: true };
  }
  return {
    ok: false,
    message: failureMessage(response, await readDetail(response)),
  };
}
