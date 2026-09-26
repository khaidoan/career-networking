"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  ChartColumn,
  CircleAlert,
  FileText,
  RotateCw,
  SearchX,
  UsersRound,
} from "lucide-react";

import { HeartToggle } from "@/components/common/heart-toggle";
import {
  DetailFields,
  DetailSection,
} from "@/components/common/detail-section";
import { ContactList } from "@/components/contacts/contact-list";
import { ApplyAction } from "@/components/jobs/apply-action";
import {
  MatchStrengthBadge,
  VisaIndicator,
} from "@/components/jobs/match-indicators";
import { ReEvaluateButton } from "@/components/jobs/re-evaluate-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOptimisticLike } from "@/hooks/use-optimistic-like";
import { getJob, setJobLiked, type JobDetail } from "@/lib/api/jobs";
import { formatLocation, formatYearsExperience } from "@/lib/jobs/format";
import { INBOX_LABELS, INBOX_PATHS } from "@/lib/jobs/inbox";
import {
  JOB_TYPE_OPTIONS,
  optionLabel,
  SENIORITY_OPTIONS,
  WORK_ARRANGEMENT_OPTIONS,
} from "@/lib/profile/options";

type LoadState =
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "ready"; job: JobDetail };

const PAGE_HEADING = "text-2xl font-semibold tracking-tight md:text-3xl";

/** Friendly page for a job that no longer exists (for example an expired Ignored job). */
export function JobNotFound() {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed bg-surface px-6 py-12 text-center">
      <SearchX aria-hidden="true" className="size-8 text-muted-foreground" />
      <h1 className={PAGE_HEADING}>Job not found</h1>
      <p className="max-w-md text-muted-foreground">
        This job may have expired or been removed. Your other jobs are still in
        your inboxes.
      </p>
      <Button asChild variant="outline">
        <Link href={INBOX_PATHS.recommended}>
          <ArrowLeft aria-hidden="true" />
          Back to inboxes
        </Link>
      </Button>
    </div>
  );
}

function ScoresSection({ job }: { job: JobDetail }) {
  const scores = [
    { label: "Overall match", value: job.overall_score },
    { label: "Experience", value: job.experience_score },
    { label: "Skills", value: job.skill_score },
    { label: "Industry experience", value: job.industry_exp_score },
  ];
  const hasScores = scores.some(({ value }) => value !== null);

  return (
    <DetailSection
      id="scores"
      title="Scores"
      description="How well this job matches your resume and preferences, out of 100."
      icon={ChartColumn}
    >
      {job.evaluation_error ? (
        <Alert variant="warning">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Not scored</AlertTitle>
          <AlertDescription>{job.evaluation_error}</AlertDescription>
        </Alert>
      ) : hasScores ? (
        <>
          {job.overall_score !== null && (
            <MatchStrengthBadge score={job.overall_score} />
          )}
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {scores.map(({ label, value }) => (
              <div
                key={label}
                className="flex flex-col gap-1 rounded-lg border bg-surface-alt px-3 py-2"
              >
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="text-xl font-semibold text-foreground">
                  {value ?? <span className="text-base">Not scored</span>}
                </dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          This job has not been scored yet.
        </p>
      )}
    </DetailSection>
  );
}

function DescriptionSection({
  job,
  onEvaluated,
}: {
  job: JobDetail;
  onEvaluated: (job: JobDetail) => void;
}) {
  return (
    <DetailSection id="description" title="Job description" icon={FileText}>
      {job.description?.trim() ? (
        // Plain text only: line breaks are kept and any HTML in the posting shows as text.
        <div className="text-sm leading-relaxed break-words whitespace-pre-line text-foreground">
          {job.description}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No description was found for this job.
        </p>
      )}
      <div className="flex flex-col gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          Score this job again against your current preferences.
        </p>
        <ReEvaluateButton
          job={job}
          onEvaluated={onEvaluated}
          className="self-start sm:self-auto"
        />
      </div>
    </DetailSection>
  );
}

function CompanySection({ job }: { job: JobDetail }) {
  const { company } = job;
  return (
    <DetailSection id="company" title="Company" icon={Building2}>
      <p className="font-medium">
        <Link
          href={`/companies/${company.id}`}
          className="inline-flex min-h-11 items-center rounded-sm text-accent underline-offset-4 hover:underline"
        >
          {company.name}
        </Link>
      </p>
      {company.description?.trim() && (
        <p className="text-sm leading-relaxed whitespace-pre-line text-foreground">
          {company.description}
        </p>
      )}
      {company.industries.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-sm text-muted-foreground">Industries</h3>
          <ul className="flex flex-wrap gap-1.5">
            {company.industries.map((industry) => (
              <li key={industry}>
                <Badge variant="secondary">{industry}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
      <DetailFields
        fields={[
          { label: "Growth stage", value: company.growth_stage },
          { label: "Employees", value: company.employee_estimate },
        ]}
      />
      {company.history?.trim() && (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-sm text-muted-foreground">History</h3>
          <p className="text-sm leading-relaxed whitespace-pre-line text-foreground">
            {company.history}
          </p>
        </div>
      )}
    </DetailSection>
  );
}

function JobHeader({
  job,
  onChange,
}: {
  job: JobDetail;
  onChange: (job: JobDetail) => void;
}) {
  const save = useCallback(
    (liked: boolean) => setJobLiked(job.id, liked),
    [job.id],
  );
  const onSaved = useCallback(
    ({ job: saved }: { job: JobDetail }) => onChange(saved),
    [onChange],
  );
  const like = useOptimisticLike({
    liked: job.liked,
    name: job.title,
    save,
    onSaved,
  });

  return (
    <header className="flex flex-col gap-4">
      <Link
        href={INBOX_PATHS[job.inbox_type]}
        className="inline-flex min-h-11 w-fit items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to {INBOX_LABELS[job.inbox_type]}
      </Link>
      <div className="flex items-start gap-2">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h1 className={`${PAGE_HEADING} break-words`}>{job.title}</h1>
          <Link
            href={`/companies/${job.company.id}`}
            className="inline-flex min-h-11 w-fit items-center rounded-sm text-lg text-accent underline-offset-4 hover:underline"
          >
            {job.company.name}
          </Link>
        </div>
        <HeartToggle
          liked={like.liked}
          name={job.title}
          onToggle={like.toggle}
          className="-mr-2"
        />
      </div>
      <VisaIndicator sponsorship={job.visa_sponsorship} />
      <DetailFields
        fields={[
          { label: "Location", value: formatLocation(job) },
          {
            label: "Work arrangement",
            value: optionLabel(WORK_ARRANGEMENT_OPTIONS, job.work_arrangement),
          },
          {
            label: "Job type",
            value: optionLabel(JOB_TYPE_OPTIONS, job.job_type_classification),
          },
          {
            label: "Seniority",
            value: optionLabel(SENIORITY_OPTIONS, job.seniority_level),
          },
          { label: "Experience", value: formatYearsExperience(job.year_exp) },
          { label: "Salary range", value: job.compensation_range },
        ]}
      />
      <ApplyAction job={job} onApplied={onChange} />
    </header>
  );
}

/**
 * Job Details: the header with Apply, the scores, the description with Re-evaluate, the
 * company and its contacts (click-to-connect). A missing job shows a friendly not-found page.
 */
export function JobDetails({ jobId }: { jobId: number }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getJob(jobId, controller.signal)
      .then((result) => {
        if (result.ok) {
          setState({ status: "ready", job: result.job });
        } else if (result.kind === "notFound") {
          setState({ status: "notFound" });
        } else {
          setState({ status: "error", message: result.message });
        }
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          throw error;
        }
      });
    return () => controller.abort();
  }, [jobId, attempt]);

  const update = useCallback((job: JobDetail) => {
    setState({ status: "ready", job });
  }, []);

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-4">
        <p role="status" className="text-sm text-muted-foreground">
          Loading job…
        </p>
        {[0, 1].map((index) => (
          <div
            key={index}
            aria-hidden="true"
            className="h-40 animate-pulse rounded-xl border bg-surface-alt"
          />
        ))}
      </div>
    );
  }

  if (state.status === "notFound") {
    return <JobNotFound />;
  }

  if (state.status === "error") {
    return (
      <div className="flex flex-col gap-6">
        <h1 className={PAGE_HEADING}>Job details</h1>
        <Alert variant="destructive">
          <AlertTitle>Could not load this job</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <p>{state.message}</p>
            <Button
              variant="outline"
              onClick={() => {
                setState({ status: "loading" });
                setAttempt((count) => count + 1);
              }}
            >
              <RotateCw aria-hidden="true" />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const { job } = state;
  return (
    <div className="flex flex-col gap-8">
      <JobHeader job={job} onChange={update} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:items-start">
        <div className="flex min-w-0 flex-col gap-6">
          <ScoresSection job={job} />
          <DescriptionSection job={job} onEvaluated={update} />
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <CompanySection job={job} />
          <DetailSection
            id="networking"
            title="Networking / Outreach"
            description="People at this company who could help with a mock interview or a referral."
            icon={UsersRound}
          >
            <ContactList
              contacts={job.contacts}
              companyName={job.company.name}
              jobTitle={job.title}
            />
          </DetailSection>
        </div>
      </div>
    </div>
  );
}
