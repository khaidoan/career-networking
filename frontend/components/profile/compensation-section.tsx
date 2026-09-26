"use client";

import { Wallet } from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { SelectField } from "@/components/profile/select-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  COUNTRY_CURRENCY,
  COUNTRY_OPTIONS,
  CURRENCY_OPTIONS,
} from "@/lib/profile/options";

type SalaryFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
};

function SalaryField({ id, label, value, onChange, error }: SalaryFieldProps) {
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={0}
        step={1}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
      />
      {error && (
        <p id={errorId} className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

/** Preferred country (which also drives the default currency) and the yearly salary range. */
export function CompensationSection({
  values,
  errors,
  onChange,
}: SectionProps) {
  function changeCountry(country: string) {
    const currency = COUNTRY_CURRENCY[country];
    onChange(currency ? { country, currency } : { country });
  }

  return (
    <ProfileSection
      id="compensation"
      title="Location & compensation"
      icon={Wallet}
      description="Only jobs in this country (or remote jobs open to it) are fetched."
    >
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <SelectField
          id="country"
          label="Country"
          value={values.country}
          onChange={changeCountry}
          options={COUNTRY_OPTIONS}
          notSetLabel="Choose a country"
          error={errors.country}
        />
        <SelectField
          id="currency"
          label="Currency"
          description="Set from the country; change it if you are paid in another currency."
          value={values.currency}
          onChange={(currency) => onChange({ currency })}
          options={CURRENCY_OPTIONS}
          notSetLabel="Choose a currency"
          error={errors.currency}
        />
        <SalaryField
          id="salary-min"
          label="Minimum yearly salary"
          value={values.salaryMin}
          onChange={(salaryMin) => onChange({ salaryMin })}
          error={errors.salary_min}
        />
        <SalaryField
          id="salary-max"
          label="Maximum yearly salary"
          value={values.salaryMax}
          onChange={(salaryMax) => onChange({ salaryMax })}
          error={errors.salary_max}
        />
      </div>
    </ProfileSection>
  );
}
