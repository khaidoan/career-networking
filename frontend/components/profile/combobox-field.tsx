"use client";

import {
  memo,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { CheckIcon, ChevronDownIcon } from "lucide-react";

import { Label } from "@/components/ui/label";
import type { Option } from "@/lib/profile/options";
import { cn } from "@/lib/utils";

/** Lower-cased with accents removed, so "cote" finds "Côte d'Ivoire". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
}

/**
 * Options matching `query`, best first: an exact code ("us"), then names starting with it, then
 * names with a word starting with it, then names containing it anywhere.
 */
export function filterOptions(
  options: readonly Option[],
  query: string,
): readonly Option[] {
  const needle = fold(query.trim());
  if (!needle) {
    return options;
  }
  const buckets: Option[][] = [[], [], [], []];
  for (const option of options) {
    const label = fold(option.label);
    if (fold(option.value) === needle) {
      buckets[0].push(option);
    } else if (label.startsWith(needle)) {
      buckets[1].push(option);
    } else if (label.split(/[\s(),'-]+/).some((w) => w.startsWith(needle))) {
      buckets[2].push(option);
    } else if (label.includes(needle)) {
      buckets[3].push(option);
    }
  }
  return buckets.flat();
}

type ComboboxFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
  description?: string;
  placeholder?: string;
  error?: string;
};

/**
 * Labelled single choice the user can type into: the list filters as they type, Enter picks the
 * highlighted match, and leaving the field (Tab or a click elsewhere) picks the highlighted match
 * for the typed text, keeps the old value when nothing matches, or clears it when the text was
 * erased. An empty string means "not set".
 *
 * Memoized like `SelectField`; pass a stable `onChange` to benefit.
 */
export const ComboboxField = memo(function ComboboxField({
  id,
  label,
  value,
  onChange,
  options,
  description,
  placeholder,
  error,
}: ComboboxFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  // The text being typed; `null` while not editing, when the input shows the chosen label.
  const [query, setQuery] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const listId = `${id}-listbox`;
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  const describedBy =
    [description ? descriptionId : null, error ? errorId : null]
      .filter(Boolean)
      .join(" ") || undefined;
  const optionId = (option: Option) => `${id}-option-${option.value}`;

  const selectedLabel =
    options.find((option) => option.value === value)?.label ?? "";
  const matches = useMemo(
    () => (query === null ? options : filterOptions(options, query)),
    [options, query],
  );
  const active = open ? matches[activeIndex] : undefined;
  const activeId = active ? optionId(active) : undefined;

  useEffect(() => {
    if (activeId) {
      // `scrollIntoView` is missing in jsdom.
      document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
    }
  }, [activeId]);

  function openList() {
    if (open) {
      return;
    }
    const selectedIndex = matches.findIndex((option) => option.value === value);
    setActiveIndex(Math.max(selectedIndex, 0));
    setOpen(true);
  }

  function commit(next: string) {
    if (next !== value) {
      onChange(next);
    }
    setQuery(null);
    setOpen(false);
  }

  /** Leaving the field: keep the typed choice if there is one, otherwise restore the old one. */
  function settle() {
    if (query === null) {
      setOpen(false);
      return;
    }
    if (!query.trim()) {
      commit("");
    } else {
      commit((matches[activeIndex] ?? matches[0])?.value ?? value);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        event.preventDefault();
        if (!open) {
          openList();
          return;
        }
        const step = event.key === "ArrowDown" ? 1 : -1;
        setActiveIndex((index) =>
          matches.length === 0
            ? 0
            : (index + step + matches.length) % matches.length,
        );
        return;
      }
      case "Enter":
        if (open) {
          // Choosing an option must not submit the form.
          event.preventDefault();
          // Erased text clears the value rather than picking the first option.
          if (active && query?.trim() !== "") {
            commit(active.value);
          } else {
            settle();
          }
        }
        return;
      case "Escape":
        if (open || query !== null) {
          event.preventDefault();
          setQuery(null);
          setOpen(false);
        }
        return;
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      {description && (
        <p id={descriptionId} className="text-sm text-muted-foreground">
          {description}
        </p>
      )}
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={activeId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder={placeholder}
          value={query ?? selectedLabel}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
            setOpen(true);
          }}
          onFocus={(event) => event.target.select()}
          onClick={openList}
          onKeyDown={handleKeyDown}
          onBlur={settle}
          className="h-11 w-full min-w-0 rounded-lg border border-input bg-surface pr-10 pl-3 text-base text-foreground shadow-soft-sm transition-colors placeholder:text-muted-foreground focus-visible:border-accent aria-invalid:border-destructive md:text-sm"
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label={open ? `Close ${label} list` : `Open ${label} list`}
          // Keep focus in the input so blurring does not settle the value.
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            inputRef.current?.focus();
            if (open) {
              setOpen(false);
            } else {
              openList();
            }
          }}
          className="absolute inset-y-0 right-0 flex w-10 cursor-pointer items-center justify-center text-muted-foreground"
        >
          <ChevronDownIcon className="size-4" aria-hidden="true" />
        </button>
        {open && (
          <ul
            id={listId}
            role="listbox"
            aria-label={label}
            className="absolute top-full z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-soft-lg"
          >
            {matches.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                No matches
              </li>
            ) : (
              matches.map((option, index) => (
                <li
                  key={option.value}
                  id={optionId(option)}
                  role="option"
                  aria-selected={option.value === value}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActiveIndex(index)}
                  onClick={() => commit(option.value)}
                  className={cn(
                    "relative flex min-h-11 cursor-pointer items-center rounded-md py-2 pr-8 pl-3 text-sm select-none",
                    option === active && "bg-accent text-accent-foreground",
                  )}
                >
                  {option.label}
                  {option.value === value && (
                    <CheckIcon
                      className="absolute right-2 size-4"
                      aria-hidden="true"
                    />
                  )}
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      {error && (
        <p id={errorId} className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
});
