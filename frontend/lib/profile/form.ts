/**
 * Profile form state and its conversions to and from the preferences API shapes.
 * Inputs hold strings (empty = not set); `toUpdate` turns them back into API values.
 */

import type {
  FieldErrors,
  Preferences,
  PreferencesUpdate,
  ResumeSuggestions,
} from "@/lib/api/preferences";
import {
  COUNTRY_CURRENCY,
  EEO_QUESTION_KEYS,
  type EeoQuestionKey,
} from "@/lib/profile/options";

export const TAG_FIELDS = [
  "desired_titles",
  "hard_skills",
  "soft_skills",
] as const;
export type TagField = (typeof TAG_FIELDS)[number];

/** Server limits from `schemas/preferences.py`. */
export const MAX_TAGS = 50;
export const MAX_TAG_LENGTH = 100;
export const MAX_ADDRESS_LENGTH = 1000;

export type ProfileFormValues = Record<TagField, string[]> & {
  country: string;
  currency: string;
  salaryMin: string;
  salaryMax: string;
  seniority: string[];
  address: string;
  gender: string;
  eeoAnswers: Record<EeoQuestionKey, string>;
  autoApply: boolean;
};

/** Lower-cased tags per field added from the latest resume upload, highlighted for review. */
export type SuggestedTags = Record<TagField, ReadonlySet<string>>;

export function emptySuggestedTags(): SuggestedTags {
  return {
    desired_titles: new Set(),
    hard_skills: new Set(),
    soft_skills: new Set(),
  };
}

/** Case-insensitive key for tag comparisons (whitespace collapsed, as on the server). */
export function tagKey(tag: string): string {
  return normalizeTag(tag).toLocaleLowerCase();
}

export function normalizeTag(tag: string): string {
  return tag.split(/\s+/).filter(Boolean).join(" ");
}

/** Append `additions` to `tags`, skipping blanks and case-insensitive duplicates. */
export function mergeTags(
  tags: readonly string[],
  additions: readonly string[],
) {
  const seen = new Set(tags.map(tagKey));
  const merged = [...tags];
  const added: string[] = [];
  for (const raw of additions) {
    const tag = normalizeTag(raw);
    const key = tag.toLocaleLowerCase();
    if (tag && !seen.has(key)) {
      seen.add(key);
      merged.push(tag);
      added.push(tag);
    }
  }
  return { tags: merged, added };
}

/**
 * Merge resume suggestions into the tag fields and mark the new ones as suggested.
 * Returns how many tags were added so the caller can tell the user.
 */
export function applySuggestions(
  values: ProfileFormValues,
  suggested: SuggestedTags,
  suggestions: ResumeSuggestions,
) {
  const nextValues = { ...values };
  const nextSuggested = { ...suggested };
  let addedCount = 0;
  for (const field of TAG_FIELDS) {
    const { tags, added } = mergeTags(values[field], suggestions[field] ?? []);
    nextValues[field] = tags;
    nextSuggested[field] = new Set([...suggested[field], ...added.map(tagKey)]);
    addedCount += added.length;
  }
  return { values: nextValues, suggested: nextSuggested, addedCount };
}

/**
 * Take the seniority, country and currency the server filled in from a resume for the fields
 * still empty in the form. A country guessed from the browser (`guessedCountry`, not saved)
 * counts as empty, and so does the currency that guess filled in.
 */
export function applyResumeDefaults(
  values: ProfileFormValues,
  saved: Pick<Preferences, "seniority" | "country" | "currency">,
  guessedCountry?: string,
): ProfileFormValues {
  const next = { ...values };
  if (next.seniority.length === 0) {
    next.seniority = saved.seniority;
  }
  const countryIsGuess =
    !next.country || (!!guessedCountry && next.country === guessedCountry);
  const guessedCurrency = guessedCountry && COUNTRY_CURRENCY[guessedCountry];
  if (saved.country && countryIsGuess) {
    next.country = saved.country;
    if (!next.currency || next.currency === guessedCurrency) {
      next.currency = saved.currency ?? "";
    }
  } else if (!next.currency && saved.currency) {
    next.currency = saved.currency;
  }
  return next;
}

export function toFormValues(preferences: Preferences): ProfileFormValues {
  const eeoAnswers = Object.fromEntries(
    EEO_QUESTION_KEYS.map((key) => [key, preferences.eeo_answers?.[key] ?? ""]),
  ) as Record<EeoQuestionKey, string>;
  return {
    desired_titles: preferences.desired_titles ?? [],
    hard_skills: preferences.hard_skills ?? [],
    soft_skills: preferences.soft_skills ?? [],
    country: preferences.country ?? "",
    currency: preferences.currency ?? "",
    salaryMin: preferences.salary_min?.toString() ?? "",
    salaryMax: preferences.salary_max?.toString() ?? "",
    seniority: preferences.seniority ?? [],
    address: preferences.address ?? "",
    gender: preferences.gender ?? "",
    eeoAnswers,
    autoApply: preferences.auto_apply ?? false,
  };
}

function parseSalary(value: string): number | null | "invalid" {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  return /^\d+$/.test(trimmed) ? Number(trimmed) : "invalid";
}

const WHOLE_NUMBER_MESSAGE = "Enter a whole number of 0 or more.";

/**
 * Client-side checks that mirror the server's salary rules, so the common mistakes are
 * caught before a request. The server still validates everything.
 */
export function validate(values: ProfileFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const min = parseSalary(values.salaryMin);
  const max = parseSalary(values.salaryMax);
  if (min === "invalid") {
    errors.salary_min = WHOLE_NUMBER_MESSAGE;
  }
  if (max === "invalid") {
    errors.salary_max = WHOLE_NUMBER_MESSAGE;
  }
  if (typeof min === "number" && typeof max === "number" && min > max) {
    errors.salary_max = "Must be greater than or equal to the minimum salary.";
  }
  return errors;
}

/** API payload for `PUT /preferences`; call only after `validate` returned no errors. */
export function toUpdate(values: ProfileFormValues): PreferencesUpdate {
  const salary = (value: string) => {
    const parsed = parseSalary(value);
    return typeof parsed === "number" ? parsed : null;
  };
  const eeoAnswers = Object.fromEntries(
    EEO_QUESTION_KEYS.map((key) => [key, values.eeoAnswers[key] || null]),
  );
  return {
    desired_titles: values.desired_titles,
    hard_skills: values.hard_skills,
    soft_skills: values.soft_skills,
    country: values.country || null,
    currency: values.currency || null,
    salary_min: salary(values.salaryMin),
    salary_max: salary(values.salaryMax),
    seniority: values.seniority,
    address: values.address.trim() || null,
    gender: values.gender || null,
    eeo_answers: eeoAnswers,
    auto_apply: values.autoApply,
  };
}

export type SetupItem = "resume" | "desired_titles" | "country";

/**
 * What the user still has to provide before the app is useful: a resume (to score jobs), plus at
 * least one desired job title and a country (the fetcher skips every run until both are saved).
 */
export function missingSetup(
  preferences: Pick<Preferences, "resume" | "desired_titles" | "country">,
): SetupItem[] {
  const missing: SetupItem[] = [];
  if (!preferences.resume) {
    missing.push("resume");
  }
  if (preferences.desired_titles.length === 0) {
    missing.push("desired_titles");
  }
  if (!preferences.country) {
    missing.push("country");
  }
  return missing;
}
