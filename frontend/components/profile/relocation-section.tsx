"use client";

import { useCallback } from "react";
import { MapPinned } from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { SelectField } from "@/components/profile/select-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { RelocationCheck } from "@/lib/api/preferences";
import { MAX_COMMUTE_MILES } from "@/lib/profile/form";
import { RELOCATION_OPTIONS } from "@/lib/profile/options";

type RelocationSectionProps = SectionProps & {
  /** How the server reads the saved address and places; refreshed on every save. */
  check: RelocationCheck;
};

/**
 * Whether the user will relocate, where they will not move to and, when they will not relocate,
 * how far they will commute. The fetcher skips on-site jobs that do not fit; remote jobs pass.
 */
export function RelocationSection({
  values,
  errors,
  onChange,
  check,
}: RelocationSectionProps) {
  const changeWilling = useCallback(
    (willingToRelocate: string) => onChange({ willingToRelocate }),
    [onChange],
  );
  const unrecognized = check.unrecognized_places;

  return (
    <ProfileSection
      id="relocation"
      title="Relocation & commute"
      icon={MapPinned}
      description="The job fetcher skips on-site and hybrid jobs that do not fit these answers; remote jobs are always kept. They are also used to answer application forms."
    >
      <SelectField
        id="willing-to-relocate"
        label="Willing to relocate"
        value={values.willingToRelocate}
        onChange={changeWilling}
        options={RELOCATION_OPTIONS}
        notSetLabel="Not answered"
        error={errors.willing_to_relocate}
      />

      <div className="flex flex-col gap-2">
        <Label htmlFor="excluded-relocation-places">
          Places I will not relocate to
        </Label>
        <p
          id="excluded-relocation-places-description"
          className="text-sm text-muted-foreground"
        >
          One state or city per line, for example: California, or Austin, TX.
          Jobs located only in these places are skipped.
        </p>
        <Textarea
          id="excluded-relocation-places"
          value={values.excludedRelocationPlaces}
          onChange={(event) =>
            onChange({ excludedRelocationPlaces: event.target.value })
          }
          rows={3}
          aria-invalid={errors.excluded_relocation_places ? true : undefined}
          aria-describedby={
            errors.excluded_relocation_places
              ? "excluded-relocation-places-description excluded-relocation-places-error"
              : "excluded-relocation-places-description"
          }
        />
        {errors.excluded_relocation_places && (
          <p
            id="excluded-relocation-places-error"
            className="text-sm font-medium text-destructive"
          >
            {errors.excluded_relocation_places}
          </p>
        )}
        {unrecognized.length > 0 && (
          <p className="text-sm font-medium text-destructive">
            Not recognized, so not used: {unrecognized.join("; ")}. Write a
            state, or a city with its state, such as Springfield, IL.
          </p>
        )}
      </div>

      {values.willingToRelocate === "no" && (
        <div className="flex flex-col gap-2">
          <Label htmlFor="max-commute-miles">Maximum commute (miles)</Label>
          <p
            id="max-commute-miles-description"
            className={
              check.home
                ? "text-sm text-muted-foreground"
                : "text-sm font-medium text-destructive"
            }
          >
            {check.home
              ? `Measured in a straight line from ${check.home}, the city in your saved address. Jobs farther away are skipped.`
              : "Add your city and state to the Address field under Personal & EEO and save; until then the commute limit is not applied."}
          </p>
          <Input
            id="max-commute-miles"
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_COMMUTE_MILES}
            step={1}
            className="sm:max-w-48"
            value={values.maxCommuteMiles}
            onChange={(event) =>
              onChange({ maxCommuteMiles: event.target.value })
            }
            aria-invalid={errors.max_commute_miles ? true : undefined}
            aria-describedby={
              errors.max_commute_miles
                ? "max-commute-miles-description max-commute-miles-error"
                : "max-commute-miles-description"
            }
          />
          {errors.max_commute_miles && (
            <p
              id="max-commute-miles-error"
              className="text-sm font-medium text-destructive"
            >
              {errors.max_commute_miles}
            </p>
          )}
        </div>
      )}
    </ProfileSection>
  );
}
