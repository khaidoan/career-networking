/** Display helpers shared by job cards, Job Details and Company Details. */

import type { JobCard } from "@/lib/api/jobs";

export type MatchStrength = "Strong" | "Good" | "Weak";

export const STRONG_MATCH_MIN = 80;
export const GOOD_MATCH_MIN = 60;

const DATE_FORMAT = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

/** City, state and country joined with commas, skipping blanks; `null` when all are missing. */
export function formatLocation(
  job: Pick<JobCard, "location_city" | "location_state" | "location_country">,
): string | null {
  const parts = [job.location_city, job.location_state, job.location_country]
    .map((part) => part?.trim())
    .filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

/** Strong (80 and up), Good (60–79) or Weak (below 60). */
export function matchStrength(score: number): MatchStrength {
  if (score >= STRONG_MATCH_MIN) {
    return "Strong";
  }
  if (score >= GOOD_MATCH_MIN) {
    return "Good";
  }
  return "Weak";
}

/** For example "Sep 25, 2026"; `null` for a missing or unparseable timestamp. */
export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : DATE_FORMAT.format(date);
}

/** For example "5+ years experience"; `null` when unknown. */
export function formatYearsExperience(years: number | null): string | null {
  if (years === null) {
    return null;
  }
  return `${years}+ ${years === 1 ? "year" : "years"} experience`;
}

const DATE_TIME_FORMAT = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});
const RELATIVE_FORMAT = new Intl.RelativeTimeFormat("en-US", {
  numeric: "auto",
});

// Largest unit first; a span is shown in the first unit it fills at least once.
const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["week", 7 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
];

/** For example "Sep 25, 2026, 2:30 PM"; `null` for a missing or unparseable timestamp. */
export function formatDateTime(iso: string | null | undefined): string | null {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : DATE_TIME_FORMAT.format(date);
}

/**
 * How long ago a past timestamp was, for example "just now", "5 minutes ago", "yesterday" or
 * "3 days ago"; `null` for a missing or unparseable timestamp. Future times (clock skew) read
 * as "just now".
 */
export function formatRelativeTime(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) {
    return null;
  }
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) {
    return null;
  }
  const seconds = Math.floor((now.getTime() - time) / 1000);
  for (const [unit, size] of RELATIVE_UNITS) {
    if (seconds >= size) {
      return RELATIVE_FORMAT.format(-Math.floor(seconds / size), unit);
    }
  }
  return "just now";
}
