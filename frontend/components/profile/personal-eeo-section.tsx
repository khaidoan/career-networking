"use client";

import { UserRound } from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { SelectField } from "@/components/profile/select-field";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_ADDRESS_LENGTH } from "@/lib/profile/form";
import {
  EEO_QUESTION_KEYS,
  EEO_QUESTIONS,
  GENDER_OPTIONS,
} from "@/lib/profile/options";

/** Address, gender and voluntary EEO answers, kept for filling in applications. */
export function PersonalEeoSection({ values, errors, onChange }: SectionProps) {
  return (
    <ProfileSection
      id="personal"
      title="Personal & EEO"
      icon={UserRound}
      description="Optional. Your address, gender, race, veteran and disability answers are never sent to the AI model."
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="address">Address</Label>
        <Textarea
          id="address"
          value={values.address}
          onChange={(event) => onChange({ address: event.target.value })}
          maxLength={MAX_ADDRESS_LENGTH}
          autoComplete="street-address"
          rows={3}
          aria-invalid={errors.address ? true : undefined}
          aria-describedby={errors.address ? "address-error" : undefined}
        />
        {errors.address && (
          <p
            id="address-error"
            className="text-sm font-medium text-destructive"
          >
            {errors.address}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <SelectField
          id="gender"
          label="Gender"
          value={values.gender}
          onChange={(gender) => onChange({ gender })}
          options={GENDER_OPTIONS}
          error={errors.gender}
        />
        {EEO_QUESTION_KEYS.map((key) => {
          const question = EEO_QUESTIONS[key];
          return (
            <SelectField
              key={key}
              id={`eeo-${key.replaceAll("_", "-")}`}
              label={question.label}
              description={question.description}
              value={values.eeoAnswers[key]}
              onChange={(answer) =>
                onChange({
                  eeoAnswers: { ...values.eeoAnswers, [key]: answer },
                })
              }
              options={question.options}
              error={errors[`eeo_answers.${key}`]}
            />
          );
        })}
      </div>
    </ProfileSection>
  );
}
