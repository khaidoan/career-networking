"use client";

import { useState, type ChangeEvent, type KeyboardEvent } from "react";
import { Sparkles, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  MAX_TAG_LENGTH,
  MAX_TAGS,
  mergeTags,
  tagKey,
} from "@/lib/profile/form";
import { cn } from "@/lib/utils";

type TagInputProps = {
  id: string;
  label: string;
  values: readonly string[];
  onChange: (values: string[]) => void;
  description?: string;
  placeholder?: string;
  /** Lower-cased tags (see `tagKey`) to show with the "suggested" style. */
  suggested?: ReadonlySet<string>;
  error?: string;
};

/**
 * Free-text tag list: Enter or comma adds the typed text as a tag (pasted comma-separated
 * text adds several), Backspace in an empty field removes the last tag, and each chip has
 * its own remove button. Duplicates are ignored case-insensitively.
 */
export function TagInput({
  id,
  label,
  values,
  onChange,
  description,
  placeholder,
  suggested,
  error,
}: TagInputProps) {
  const [draft, setDraft] = useState("");
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  const full = values.length >= MAX_TAGS;

  function add(parts: string[]) {
    const room = MAX_TAGS - values.length;
    const { tags, added } = mergeTags(values, parts);
    if (added.length > 0 && room > 0) {
      onChange(tags.slice(0, values.length + room));
    }
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const text = event.target.value;
    if (!text.includes(",")) {
      setDraft(text);
      return;
    }
    // Everything before the last comma is complete; the rest stays in the field.
    const parts = text.split(",");
    const rest = parts.pop() ?? "";
    add(parts);
    setDraft(rest.trimStart());
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      add([draft]);
      setDraft("");
    } else if (event.key === "Backspace" && draft === "" && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  }

  function handleBlur() {
    // Keep text the user typed but did not confirm, so it is not lost on Save.
    if (draft.trim()) {
      add([draft]);
      setDraft("");
    }
  }

  function remove(index: number) {
    onChange(values.filter((_, i) => i !== index));
  }

  const describedBy =
    [description ? descriptionId : null, error ? errorId : null]
      .filter(Boolean)
      .join(" ") || undefined;

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      {description && (
        <p id={descriptionId} className="text-sm text-muted-foreground">
          {description}
        </p>
      )}
      {values.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label={`${label} tags`}>
          {values.map((tag, index) => {
            const isSuggested = suggested?.has(tagKey(tag)) ?? false;
            return (
              <li
                key={tagKey(tag)}
                className={cn(
                  "inline-flex max-w-full items-center gap-1 rounded-full border py-0.5 pr-0.5 pl-3 text-sm",
                  isSuggested
                    ? "border-dashed border-accent bg-surface text-foreground"
                    : "border-transparent bg-surface-alt text-foreground",
                )}
              >
                {isSuggested && (
                  <Sparkles
                    className="size-3.5 shrink-0 text-accent"
                    aria-hidden="true"
                  />
                )}
                <span className="truncate">{tag}</span>
                {isSuggested && <span className="sr-only">(suggested)</span>}
                <button
                  type="button"
                  onClick={() => remove(index)}
                  className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-border hover:text-foreground"
                  aria-label={`Remove ${tag}`}
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <Input
        id={id}
        value={draft}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        placeholder={
          full
            ? `Limit of ${MAX_TAGS} reached`
            : (placeholder ?? "Type and press Enter")
        }
        disabled={full}
        maxLength={MAX_TAG_LENGTH}
        enterKeyHint="enter"
        autoComplete="off"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {error && (
        <p id={errorId} className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
