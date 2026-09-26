"use client";

import { BriefcaseBusiness } from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { TagInput } from "@/components/profile/tag-input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { SuggestedTags } from "@/lib/profile/form";
import { SENIORITY_OPTIONS } from "@/lib/profile/options";

type JobPreferencesSectionProps = SectionProps & { suggested: SuggestedTags };

/** Desired titles, hard and soft skills, and the seniority levels to look for. */
export function JobPreferencesSection({
  values,
  errors,
  onChange,
  suggested,
}: JobPreferencesSectionProps) {
  function toggleSeniority(level: string, checked: boolean) {
    const selected = new Set(values.seniority);
    if (checked) {
      selected.add(level);
    } else {
      selected.delete(level);
    }
    // Keep the fixed display order rather than click order.
    onChange({
      seniority: SENIORITY_OPTIONS.map((option) => option.value).filter(
        (value) => selected.has(value),
      ),
    });
  }

  return (
    <ProfileSection
      id="job-preferences"
      title="Job preferences"
      icon={BriefcaseBusiness}
      description="The job fetcher searches for these titles and scores each job against your skills."
    >
      <TagInput
        id="desired-titles"
        label="Desired job titles"
        description="For example: Backend Engineer. Jobs must contain every word of a title."
        values={values.desired_titles}
        onChange={(desired_titles) => onChange({ desired_titles })}
        suggested={suggested.desired_titles}
        error={errors.desired_titles}
      />
      <TagInput
        id="hard-skills"
        label="Hard skills"
        description="Tools, languages and technical skills."
        values={values.hard_skills}
        onChange={(hard_skills) => onChange({ hard_skills })}
        suggested={suggested.hard_skills}
        error={errors.hard_skills}
      />
      <TagInput
        id="soft-skills"
        label="Soft skills"
        description="For example: mentoring, stakeholder management."
        values={values.soft_skills}
        onChange={(soft_skills) => onChange({ soft_skills })}
        suggested={suggested.soft_skills}
        error={errors.soft_skills}
      />

      <fieldset
        className="flex flex-col gap-3"
        aria-describedby={errors.seniority ? "seniority-error" : undefined}
      >
        <legend className="mb-3 text-sm leading-none font-medium">
          Seniority
        </legend>
        <div className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
          {SENIORITY_OPTIONS.map((option) => {
            const id = `seniority-${option.value}`;
            return (
              <div
                key={option.value}
                className="flex min-h-11 items-center gap-3"
              >
                <Checkbox
                  id={id}
                  checked={values.seniority.includes(option.value)}
                  onCheckedChange={(checked) =>
                    toggleSeniority(option.value, checked === true)
                  }
                />
                <Label htmlFor={id} className="cursor-pointer font-normal">
                  {option.label}
                </Label>
              </div>
            );
          })}
        </div>
        {errors.seniority && (
          <p
            id="seniority-error"
            className="text-sm font-medium text-destructive"
          >
            {errors.seniority}
          </p>
        )}
      </fieldset>
    </ProfileSection>
  );
}
