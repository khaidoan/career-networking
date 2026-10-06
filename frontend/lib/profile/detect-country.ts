import { COUNTRY_OPTIONS } from "@/lib/profile/options";
import { TIMEZONE_COUNTRIES } from "@/lib/profile/timezone-countries";

const KNOWN_COUNTRIES = new Set(COUNTRY_OPTIONS.map((option) => option.value));

type BrowserHints = {
  timeZone?: string;
  languages?: readonly string[];
};

function browserHints(): BrowserHints {
  let timeZone: string | undefined;
  try {
    timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    // Very old browsers; fall back to the languages.
  }
  const languages =
    typeof navigator === "undefined" ? [] : (navigator.languages ?? []);
  return { timeZone, languages };
}

function regionOf(language: string): string | undefined {
  try {
    // Only an explicit region counts: "en" alone says nothing about where the user is.
    return new Intl.Locale(language).region;
  } catch {
    return undefined;
  }
}

/**
 * Best guess at the user's current country from the browser alone (nothing is sent anywhere):
 * the time zone first, as it follows where the device is, then the region of the preferred
 * languages ("en-GB" → GB). `undefined` when neither names a known country.
 */
export function detectCountry(
  hints: BrowserHints = browserHints(),
): string | undefined {
  const fromTimeZone = hints.timeZone && TIMEZONE_COUNTRIES[hints.timeZone];
  if (fromTimeZone && KNOWN_COUNTRIES.has(fromTimeZone)) {
    return fromTimeZone;
  }
  for (const language of hints.languages ?? []) {
    const region = regionOf(language);
    if (region && KNOWN_COUNTRIES.has(region)) {
      return region;
    }
  }
  return undefined;
}
