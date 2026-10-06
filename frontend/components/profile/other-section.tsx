"use client";

import { useCallback, useState } from "react";
import { Settings2 } from "lucide-react";

import { ComboboxField } from "@/components/profile/combobox-field";
import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_ADDITIONAL_INFORMATION_LENGTH } from "@/lib/profile/form";
import { timeZoneOptions } from "@/lib/profile/timezones";

type OtherSectionProps = SectionProps & {
  /** Time zone guessed from the browser and not saved yet; the field says so while chosen. */
  detectedTimeZone?: string;
};

/**
 * Settings that do not belong to another section: the daily fetch time, additional information
 * and auto apply.
 */
export function OtherSection({
  values,
  errors,
  onChange,
  detectedTimeZone,
}: OtherSectionProps) {
  // Built once; the saved or detected name is added in case the browser's list lacks it.
  const [zones] = useState(() => timeZoneOptions([values.fetchTimezone]));
  const changeTimeZone = useCallback(
    (fetchTimezone: string) => onChange({ fetchTimezone }),
    [onChange],
  );

  return (
    <ProfileSection
      id="other"
      title="Other"
      icon={Settings2}
      description="Other settings for your job search."
    >
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="fetch-time">Daily job fetch time</Label>
          <p
            id="fetch-time-description"
            className="text-sm text-muted-foreground"
          >
            Required for job fetching. New jobs are fetched once a day at this
            time, and whenever the server restarts.
          </p>
          <Input
            id="fetch-time"
            type="time"
            step={60}
            required
            value={values.fetchTime}
            onChange={(event) => onChange({ fetchTime: event.target.value })}
            aria-invalid={errors.fetch_time ? true : undefined}
            aria-describedby={
              errors.fetch_time
                ? "fetch-time-description fetch-time-error"
                : "fetch-time-description"
            }
          />
          {errors.fetch_time && (
            <p
              id="fetch-time-error"
              className="text-sm font-medium text-destructive"
            >
              {errors.fetch_time}
            </p>
          )}
        </div>
        <ComboboxField
          id="fetch-timezone"
          label="Time zone"
          description={
            detectedTimeZone && values.fetchTimezone === detectedTimeZone
              ? "Detected from your browser. Check it, then click Save."
              : "The fetch time is in this time zone."
          }
          value={values.fetchTimezone}
          onChange={changeTimeZone}
          options={zones}
          placeholder="Type to search time zones"
          error={errors.fetch_timezone}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="additional-information">Additional Information</Label>
        <p
          id="additional-information-description"
          className="text-sm text-muted-foreground"
        >
          A longer version of your resume: projects, accomplishments and details
          that did not fit on your uploaded resume, plus anything else for
          applications, such as your notice period or earliest start date. It is
          used to fill in application forms and to write your tailored resume
          and cover letter.
        </p>
        <Textarea
          id="additional-information"
          value={values.additionalInformation}
          onChange={(event) =>
            onChange({ additionalInformation: event.target.value })
          }
          rows={10}
          maxLength={MAX_ADDITIONAL_INFORMATION_LENGTH}
          aria-invalid={errors.additional_information ? true : undefined}
          aria-describedby={
            errors.additional_information
              ? "additional-information-description additional-information-error"
              : "additional-information-description"
          }
        />
        {errors.additional_information && (
          <p
            id="additional-information-error"
            className="text-sm font-medium text-destructive"
          >
            {errors.additional_information}
          </p>
        )}
      </div>

      <div className="flex items-start gap-3">
        <Checkbox
          id="auto-apply"
          className="mt-0.5"
          checked={values.autoApply}
          onCheckedChange={(checked) =>
            onChange({ autoApply: checked === true })
          }
          aria-describedby="auto-apply-description"
        />
        <div className="flex flex-col gap-1">
          <Label htmlFor="auto-apply" className="cursor-pointer">
            Auto apply
          </Label>
          <p
            id="auto-apply-description"
            className="text-sm text-muted-foreground"
          >
            Allow applications to be submitted for you automatically. Off by
            default.
          </p>
        </div>
      </div>
    </ProfileSection>
  );
}
