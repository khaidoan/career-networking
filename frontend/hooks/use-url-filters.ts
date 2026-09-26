"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** New values per query parameter: a list repeats the key, `null` or `[]` removes it. */
export type FilterChanges = Record<string, string | readonly string[] | null>;

export const SEARCH_DEBOUNCE_MS = 300;

/** Apply `changes` to a copy of `params`, dropping empty values. */
export function withChanges(
  params: URLSearchParams,
  changes: FilterChanges,
): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const [key, value] of Object.entries(changes)) {
    next.delete(key);
    const values = typeof value === "string" ? [value] : (value ?? []);
    for (const item of values) {
      if (item) {
        next.append(key, item);
      }
    }
  }
  return next;
}

/**
 * Filter and search state kept in the URL query string, so it survives a refresh and can be
 * shared. Updates replace the history entry and keep the scroll position.
 */
export function useUrlFilters() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  // Debounced writes read the latest params, not the ones from when the timer started.
  const latest = useRef<URLSearchParams>(new URLSearchParams(searchParams));

  useEffect(() => {
    latest.current = new URLSearchParams(searchParams);
  }, [searchParams]);

  const setFilters = useCallback(
    (changes: FilterChanges) => {
      const next = withChanges(latest.current, changes);
      latest.current = next;
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router],
  );

  return { searchParams, setFilters };
}

/**
 * A text input bound to one query parameter: typing updates the input at once and the URL after
 * a pause; a URL change from elsewhere (e.g. "Clear filters") replaces the text.
 */
export function useDebouncedSearchParam(
  key: string,
  delay = SEARCH_DEBOUNCE_MS,
) {
  const { searchParams, setFilters } = useUrlFilters();
  const urlValue = searchParams.get(key) ?? "";
  const [text, setText] = useState(urlValue);
  const [seenUrlValue, setSeenUrlValue] = useState(urlValue);
  const [writtenValue, setWrittenValue] = useState(urlValue);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (urlValue !== seenUrlValue) {
    setSeenUrlValue(urlValue);
    if (urlValue !== writtenValue) {
      setText(urlValue);
      setWrittenValue(urlValue);
    }
  }

  useEffect(
    () => () => {
      if (timer.current) {
        clearTimeout(timer.current);
      }
    },
    [],
  );

  const onTextChange = useCallback(
    (value: string) => {
      setText(value);
      if (timer.current) {
        clearTimeout(timer.current);
      }
      timer.current = setTimeout(() => {
        const trimmed = value.trim();
        setWrittenValue(trimmed);
        setFilters({ [key]: trimmed || null });
      }, delay);
    },
    [delay, key, setFilters],
  );

  return [text, onTextChange] as const;
}
