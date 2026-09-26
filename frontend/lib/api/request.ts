/**
 * Shared plumbing for the browser-side API clients (`lib/api/*`). Calls go to the same-origin
 * `/api/v1/...` (proxied to the jobs service) with the session cookie (`credentials: "include"`),
 * and every failure resolves to a typed result with a user-facing message instead of throwing.
 */

import { NETWORK_ERROR_MESSAGE } from "@/lib/auth/client";

export { NETWORK_ERROR_MESSAGE };
export const SESSION_EXPIRED_MESSAGE =
  "Your session has expired. Sign in again to continue.";
export const UNEXPECTED_ERROR_MESSAGE =
  "Something went wrong. Please try again.";
export const INVALID_INPUT_MESSAGE =
  "Some fields need your attention. Check the messages below.";

/** Field-level messages keyed by field name (`eeo_answers.<key>` for EEO questions). */
export type FieldErrors = Record<string, string>;

export type Failure = { ok: false; message: string };

/** Why a call failed, so callers can react to a missing record or a conflict specifically. */
export type FailureKind =
  | "network"
  | "sessionExpired"
  | "notFound"
  | "conflict"
  | "invalid"
  | "unexpected";

export type ApiFailure = Failure & {
  kind: FailureKind;
  /** Per-field messages from a 422 response; empty for every other failure. */
  fieldErrors: FieldErrors;
};

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

type ValidationIssue = { loc?: unknown[]; msg?: unknown };

// FastAPI prefixes each 422 `loc` with where the value came from.
const LOCATION_PREFIXES = new Set(["body", "query", "path"]);

/** `fetch` with the session cookie; `null` on a network failure. Aborts are rethrown. */
export async function request(
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

/** The `detail` of a JSON error body, or `undefined` when the body is not JSON. */
export async function readDetail(response: Response): Promise<unknown> {
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

export function failureMessage(response: Response, detail: unknown): string {
  if (response.status === 401) {
    return SESSION_EXPIRED_MESSAGE;
  }
  // The API's own messages (400/404/409/413/415/422 with a string detail) are written for users.
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
    const path =
      typeof loc[0] === "string" && LOCATION_PREFIXES.has(loc[0])
        ? loc.slice(1)
        : loc;
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

function failureKind(status: number): FailureKind {
  switch (status) {
    case 401:
      return "sessionExpired";
    case 404:
      return "notFound";
    case 409:
      return "conflict";
    case 422:
      return "invalid";
    default:
      return "unexpected";
  }
}

/** The typed failure for a non-2xx response. */
export async function toFailure(response: Response): Promise<ApiFailure> {
  const detail = await readDetail(response);
  const kind = failureKind(response.status);
  const fieldErrors = kind === "invalid" ? fieldErrorsFromDetail(detail) : {};
  const message =
    Object.keys(fieldErrors).length > 0
      ? INVALID_INPUT_MESSAGE
      : failureMessage(response, detail);
  return { ok: false, kind, message, fieldErrors };
}

/**
 * Call the API and parse the JSON body. A `204 No Content` answer resolves with `undefined`
 * data; aborting through `init.signal` rejects with the `AbortError`.
 */
export async function requestJson<T>(
  input: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const response = await request(input, init);
  if (!response) {
    return {
      ok: false,
      kind: "network",
      message: NETWORK_ERROR_MESSAGE,
      fieldErrors: {},
    };
  }
  if (!response.ok) {
    return toFailure(response);
  }
  if (response.status === 204) {
    return { ok: true, data: undefined as T };
  }
  return { ok: true, data: (await response.json()) as T };
}

/** `RequestInit` for a JSON body with the given method. */
export function jsonBody(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
