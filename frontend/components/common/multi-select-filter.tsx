"use client";

import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Option } from "@/lib/profile/options";
import { cn } from "@/lib/utils";

type MultiSelectFilterProps = {
  id: string;
  label: string;
  options: readonly Option[];
  selected: readonly string[];
  onChange: (values: string[]) => void;
  /** Shown when there are no options to pick from. */
  emptyMessage?: string;
  className?: string;
};

function summary(options: readonly Option[], selected: readonly string[]) {
  if (selected.length === 0) {
    return "Any";
  }
  if (selected.length === 1) {
    return (
      options.find((option) => option.value === selected[0])?.label ??
      selected[0]
    );
  }
  return `${selected.length} selected`;
}

/**
 * Labelled multi-select dropdown. The button reads as "{label} {summary}" (e.g. "Seniority
 * 2 selected") and the menu stays open while options are toggled.
 */
export function MultiSelectFilter({
  id,
  label,
  options,
  selected,
  onChange,
  emptyMessage = "No options yet",
  className,
}: MultiSelectFilterProps) {
  const labelId = `${id}-label`;
  const valueId = `${id}-value`;

  function toggle(value: string, checked: boolean) {
    onChange(
      checked
        ? options
            .map((option) => option.value)
            .filter((item) => item === value || selected.includes(item))
        : selected.filter((item) => item !== value),
    );
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <span
        id={labelId}
        className="text-sm leading-none font-medium text-foreground"
      >
        {label}
      </span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            id={id}
            variant="outline"
            aria-labelledby={`${labelId} ${valueId}`}
            className="w-full justify-between font-normal"
          >
            <span id={valueId} className="truncate">
              {summary(options, selected)}
            </span>
            <ChevronDown aria-hidden="true" className="text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          aria-labelledby={labelId}
          className="max-h-80"
        >
          {options.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              {emptyMessage}
            </p>
          ) : (
            options.map((option) => (
              <DropdownMenuCheckboxItem
                key={option.value}
                checked={selected.includes(option.value)}
                onCheckedChange={(checked) =>
                  toggle(option.value, checked === true)
                }
                onSelect={(event) => event.preventDefault()}
              >
                {option.label}
              </DropdownMenuCheckboxItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
