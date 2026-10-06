"use client";

import { Settings2 } from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import type { SectionProps } from "@/components/profile/section-props";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

/** Settings that do not belong to another section, such as auto apply. */
export function OtherSection({ values, onChange }: SectionProps) {
  return (
    <ProfileSection
      id="other"
      title="Other"
      icon={Settings2}
      description="Other settings for your job search."
    >
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
