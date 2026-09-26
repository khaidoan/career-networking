"use client";

import { useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Banknote,
  Briefcase,
  Clock,
  Factory,
  Laptop,
  Layers,
  MapPin,
  Sprout,
  type LucideIcon,
} from "lucide-react";

import { HeartToggle } from "@/components/common/heart-toggle";
import {
  MatchStrengthBadge,
  NotScoredBadge,
  VisaIndicator,
} from "@/components/jobs/match-indicators";
import { ReEvaluateButton } from "@/components/jobs/re-evaluate-button";
import { Card } from "@/components/ui/card";
import { useOptimisticLike } from "@/hooks/use-optimistic-like";
import { setJobLiked, type JobCard as JobCardData } from "@/lib/api/jobs";
import { formatLocation, formatYearsExperience } from "@/lib/jobs/format";
import {
  JOB_TYPE_OPTIONS,
  optionLabel,
  SENIORITY_OPTIONS,
  WORK_ARRANGEMENT_OPTIONS,
} from "@/lib/profile/options";
import { cn } from "@/lib/utils";

type JobCardProps = {
  job: JobCardData;
  /** Receives the saved job after a like or a re-evaluation. */
  onChange: (job: JobCardData) => void;
  /**
   * Company Details variant: the title is an `h3` under the page's Jobs section and the
   * company name, industry and growth stage (shown on that page already) are left out.
   */
  compact?: boolean;
  className?: string;
};

type Detail = { label: string; value: string | null; icon: LucideIcon };

function companyDetails(job: JobCardData): Detail[] {
  return [
    {
      label: "Industry",
      value: job.company_industries.join(", ") || null,
      icon: Factory,
    },
    { label: "Growth stage", value: job.company_growth_stage, icon: Sprout },
  ];
}

function jobDetails(job: JobCardData): Detail[] {
  return [
    { label: "Location", value: formatLocation(job), icon: MapPin },
    {
      label: "Work arrangement",
      value: optionLabel(WORK_ARRANGEMENT_OPTIONS, job.work_arrangement),
      icon: Laptop,
    },
    {
      label: "Job type",
      value: optionLabel(JOB_TYPE_OPTIONS, job.job_type_classification),
      icon: Briefcase,
    },
    { label: "Salary range", value: job.compensation_range, icon: Banknote },
    {
      label: "Seniority",
      value: optionLabel(SENIORITY_OPTIONS, job.seniority_level),
      icon: Layers,
    },
    {
      label: "Experience",
      value: formatYearsExperience(job.year_exp),
      icon: Clock,
    },
  ];
}

/**
 * One job in an inbox list (render inside a `ul`). The whole card opens Job Details through the
 * title link; the like and Re-evaluate buttons sit above that link. Unknown values are hidden.
 */
export function JobCard({
  job,
  onChange,
  compact = false,
  className,
}: JobCardProps) {
  const save = useCallback(
    (liked: boolean) => setJobLiked(job.id, liked),
    [job.id],
  );
  const onSaved = useCallback(
    ({ job: saved }: { job: JobCardData }) => onChange(saved),
    [onChange],
  );
  const like = useOptimisticLike({
    liked: job.liked,
    name: job.title,
    save,
    onSaved,
  });
  const titleRef = useRef<HTMLAnchorElement>(null);
  const restoreFocus = useRef(false);
  const handleEvaluated = useCallback(
    (updated: JobCardData) => {
      // A successful re-evaluation removes the Re-evaluate button that had focus.
      restoreFocus.current = !updated.evaluation_error;
      onChange(updated);
    },
    [onChange],
  );
  useEffect(() => {
    if (!restoreFocus.current || job.evaluation_error) {
      return;
    }
    restoreFocus.current = false;
    // Only recover focus that was lost; never pull it away from somewhere the user moved to.
    if (!document.activeElement || document.activeElement === document.body) {
      titleRef.current?.focus();
    }
  }, [job.evaluation_error]);
  const details = [
    ...(compact ? [] : companyDetails(job)),
    ...jobDetails(job),
  ].filter((detail) => detail.value);
  const Heading = compact ? "h3" : "h2";

  return (
    <li>
      <Card
        className={cn("relative gap-4 px-4 py-4 md:px-6 md:py-5", className)}
      >
        <div className="flex items-start gap-2">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <Heading className="text-lg leading-snug font-semibold text-foreground">
              <Link
                ref={titleRef}
                href={`/jobs/${job.id}`}
                className="rounded-sm underline-offset-4 after:absolute after:inset-0 after:rounded-xl hover:underline"
              >
                {job.title}
              </Link>
            </Heading>
            {!compact && (
              <p className="text-sm text-muted-foreground">
                {job.company_name}
              </p>
            )}
          </div>
          <HeartToggle
            liked={like.liked}
            name={job.title}
            onToggle={like.toggle}
            className="relative z-10 -mt-1 -mr-2"
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {job.evaluation_error ? (
            <NotScoredBadge />
          ) : (
            job.overall_score !== null && (
              <MatchStrengthBadge score={job.overall_score} />
            )
          )}
          <VisaIndicator sponsorship={job.visa_sponsorship} />
        </div>

        {details.length > 0 && (
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {details.map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex min-w-0 items-start gap-2">
                <dt className="flex shrink-0 items-center">
                  <Icon
                    aria-hidden="true"
                    className="mt-0.5 size-4 text-muted-foreground"
                  />
                  <span className="sr-only">{label}</span>
                </dt>
                <dd className="min-w-0 text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        )}

        {job.evaluation_error && (
          <div className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                Why it was not scored:{" "}
              </span>
              {job.evaluation_error}
            </p>
            <ReEvaluateButton
              job={job}
              onEvaluated={handleEvaluated}
              className="relative z-10 self-start sm:self-auto"
            />
          </div>
        )}
      </Card>
    </li>
  );
}
