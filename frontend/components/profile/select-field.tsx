"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Option } from "@/lib/profile/options";

// Radix Select cannot hold an empty value, so "not set" uses a sentinel item.
const NOT_SET = "__not_set__";

type SelectFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
  description?: string;
  /** Label of the item that clears the value. */
  notSetLabel?: string;
  error?: string;
};

/** Labelled single-choice Select; an empty string means "not set". */
export function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  description,
  notSetLabel = "Not set",
  error,
}: SelectFieldProps) {
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
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
      <Select
        value={value || NOT_SET}
        onValueChange={(next) => onChange(next === NOT_SET ? "" : next)}
      >
        <SelectTrigger
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NOT_SET}>{notSetLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && (
        <p id={errorId} className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
