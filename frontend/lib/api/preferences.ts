/**
 * Browser-side calls to the same-origin preferences API (`/api/v1/preferences`, proxied to the
 * jobs service). Follows `lib/auth/client.ts`: the session cookie is sent with
 * `credentials: "include"` and every call resolves to a typed result instead of throwing.
 */

import { NETWORK_ERROR_MESSAGE } from "@/lib/auth/client";
import type { EeoQuestionKey } from "@/lib/profile/options";

const PREFERENCES_API = "/api/v1/preferences";

export { NETWORK_ERROR_MESSAGE };
export const SESSION_EXPIRED_MESSAGE =
  "Your session has expired. Sign in again to continue.";
export const UNEXPECTED_ERROR_MESSAGE =
  "Something went wrong. Please try again.";
export const INVALID_PREFERENCES_MESSAGE =
  "Some fields need your attention. Check the messages below.";
export const RESUME_TOO_LARGE_MESSAGE =
  "The resume is larger than 10 MB. Upload a smaller file.";
export const RESUME_WRONG_TYPE_MESSAGE =
  "Only PDF (.pdf) and Word (.docx) resumes are supported.";

export type ResumeFileType = "pdf" | "docx";

export type ResumeInfo = {
  file_type: ResumeFileType;
  /** ISO 8601 timestamp of the last upload. */
  uploaded_at: string;
};

export type EeoAnswers = Partial<Record<EeoQuestionKey, string | null>>;

/** Every editable preference; `PUT` replaces all of them at once. */
export type PreferencesUpdate = {
  desired_titles: string[];
  hard_skills: string[];
  soft_skills: string[];
  country: string | null;
  currency: string | null;
  salary_min: number | null;
  salary_max: number | null;
  seniority: string[];
  address: string | null;
  gender: string | null;
  eeo_answers: EeoAnswers;
};

export type Preferences = PreferencesUpdate & { resume: ResumeInfo | null };

export type ResumeSuggestions = {
  desired_titles: string[];
  hard_skills: string[];
  soft_skills: string[];
};

export type ResumeUpload = {
  resume: ResumeInfo;
  /** `null` when the model could not produce suggestions; `warning` then says why. */
  suggestions: ResumeSuggestions | null;
  warning: string | null;
};

/** Field-level messages keyed by field name (`eeo_answers.<key>` for EEO questions). */
export type FieldErrors = Record<string, string>;

export type Failure = { ok: false; message: string };
export type PreferencesResult =
  { ok: true; preferences: Preferences } | Failure;
export type SaveResult =
  | { ok: true; preferences: Preferences }
  | (Failure & { fieldErrors: FieldErrors });
export type UploadResult = ({ ok: true } & ResumeUpload) | Failure;
export type DeleteResult = { ok: true } | Failure;

type ValidationIssue = { loc?: unknown[]; msg?: unknown };

async function request(
  input: string,
  init: RequestInit = {},
): Promise<Response | null> {
  try {
    return await fetch(input, { ...init, credentials: "include" });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    return null;
  }
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      return body.detail;
    }
  } catch {
    // Not JSON (e.g. an nginx error page).
  }
  return undefined;
}

function failureMessage(response: Response, detail: unknown): string {
  if (response.status === 401) {
    return SESSION_EXPIRED_MESSAGE;
  }
  // The API's own messages (400/413/415/422 with a string detail) are written for users.
  if (typeof detail === "string" && response.status < 500) {
    return detail;
  }
  return UNEXPECTED_ERROR_MESSAGE;
}

/**
 * Map FastAPI's 422 `detail` list to one message per field, e.g.
 * `{loc: ["body", "salary_max"], msg: "Value error, must be ..."}` -> `{salary_max: "Must be ..."}`.
 */
export function fieldErrorsFromDetail(detail: unknown): FieldErrors {
  const errors: FieldErrors = {};
  if (!Array.isArray(detail)) {
    return errors;
  }
  for (const issue of detail as ValidationIssue[]) {
    const loc = Array.isArray(issue?.loc) ? issue.loc : [];
    const path = loc[0] === "body" ? loc.slice(1) : loc;
    const [field, sub] = path;
    if (typeof field !== "string") {
      continue;
    }
    const key =
      field === "eeo_answers" && typeof sub === "string"
        ? `eeo_answers.${sub}`
        : field;
    if (key in errors || typeof issue.msg !== "string") {
      continue;
    }
    const message = issue.msg.replace(/^Value error,\s*/, "");
    errors[key] = message.charAt(0).toUpperCase() + message.slice(1);
  }
  return errors;
}

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
