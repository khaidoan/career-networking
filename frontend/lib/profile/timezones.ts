import type { Option } from "@/lib/profile/options";

/** The browser's IANA time zone, or `undefined` if it cannot tell. */
export function browserTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

/**
 * Every time zone the browser knows, plus UTC and `include` (a saved or detected name such as
 * the legacy "Asia/Calcutta" that the list may leave out), labelled without underscores.
 */
export function timeZoneOptions(include: readonly string[] = []): Option[] {
  let names: string[] = [];
  try {
    names = Intl.supportedValuesOf("timeZone");
  } catch {
    // Older browsers: only UTC and the given names.
  }
  const unique = [...new Set(["UTC", ...names, ...include.filter(Boolean)])];
  return unique
    .sort((a, b) => a.localeCompare(b, "en"))
    .map((name) => ({ value: name, label: name.replaceAll("_", " ") }));
}
