import type { FieldErrors } from "@/lib/api/preferences";
import type { ProfileFormValues } from "@/lib/profile/form";

/** Shared props of the Profile form sections: values in, partial updates out. */
export type SectionProps = {
  values: ProfileFormValues;
  errors: FieldErrors;
  onChange: (patch: Partial<ProfileFormValues>) => void;
};
