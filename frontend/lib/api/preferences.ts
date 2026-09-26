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
