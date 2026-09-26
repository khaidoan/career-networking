"use client";

import { useCallback } from "react";
import Link from "next/link";
import { Sprout, UsersRound, type LucideIcon } from "lucide-react";

import { CompanyActions } from "@/components/companies/company-actions";
import { HeartToggle } from "@/components/common/heart-toggle";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useOptimisticLike } from "@/hooks/use-optimistic-like";
import {
  setCompanyLiked,
  type CompanyCard as CompanyCardData,
  type CompanyDetail,
} from "@/lib/api/companies";
import { cn } from "@/lib/utils";

type CompanyCardProps = {
  company: CompanyCardData;
  /** Receives the saved company after a like. */
  onChange: (company: CompanyCardData) => void;
  /** Receives the saved company after an edit. */
  onEdited: (company: CompanyCardData) => void;
  onDeleted: (companyId: number) => void;
  className?: string;
};

type Detail = { label: string; value: string | null; icon: LucideIcon };

/** The list fields of a saved company (the API returns every field). */
function toCard(company: CompanyDetail): CompanyCardData {
  return {
    id: company.id,
    name: company.name,
    logo_url: company.logo_url,
    industries: company.industries,
    growth_stage: company.growth_stage,
    employee_estimate: company.employee_estimate,
    liked: company.liked,
  };
}

/**
 * One company in the Companies list (render inside a `ul`): the name links to Company Details,
 * with like, edit and delete buttons. Unknown values are hidden.
 */
export function CompanyCard({
  company,
  onChange,
  onEdited,
  onDeleted,
  className,
}: CompanyCardProps) {
  const save = useCallback(
    (liked: boolean) => setCompanyLiked(company.id, liked),
    [company.id],
  );
  const onLikeSaved = useCallback(
    ({ company: saved }: { company: CompanyDetail }) => onChange(toCard(saved)),
    [onChange],
  );
  const like = useOptimisticLike({
    liked: company.liked,
    name: company.name,
    save,
    onSaved: onLikeSaved,
  });

  const details: Detail[] = [
    { label: "Growth stage", value: company.growth_stage, icon: Sprout },
    { label: "Employees", value: company.employee_estimate, icon: UsersRound },
  ].filter((detail) => detail.value);

  return (
    <li>
      <Card className={cn("gap-3 px-4 py-4 md:px-6 md:py-5", className)}>
        <div className="flex items-start gap-2">
          <h2 className="min-w-0 flex-1 pt-2 text-lg leading-snug font-semibold break-words text-foreground">
            <Link
              href={`/companies/${company.id}`}
              className="rounded-sm underline-offset-4 hover:underline"
            >
              {company.name}
            </Link>
          </h2>
          <div className="-mr-2 flex shrink-0 items-center">
            <HeartToggle
              liked={like.liked}
              name={company.name}
              onToggle={like.toggle}
            />
            <CompanyActions
              company={company}
              variant="icon"
              onSaved={(saved) => onEdited(toCard(saved))}
              onDeleted={() => onDeleted(company.id)}
            />
          </div>
        </div>

        {company.industries.length > 0 && (
          <ul
            aria-label={`${company.name} industries`}
            className="flex flex-wrap gap-1.5"
          >
            {company.industries.map((industry) => (
              <li key={industry}>
                <Badge variant="outline">{industry}</Badge>
              </li>
            ))}
          </ul>
        )}

        {details.length > 0 && (
          <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {details.map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex min-w-0 items-center gap-2">
                <dt className="flex shrink-0 items-center gap-1.5 text-muted-foreground">
                  <Icon aria-hidden="true" className="size-4" />
                  {label}
                </dt>
                <dd className="min-w-0 text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </Card>
    </li>
  );
}
