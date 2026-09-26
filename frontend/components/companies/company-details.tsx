"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  ExternalLink,
  Globe,
  SearchX,
  UsersRound,
} from "lucide-react";

import { CompanyActions } from "@/components/companies/company-actions";
import { HeartToggle } from "@/components/common/heart-toggle";
import {
  DetailFields,
  DetailSection,
} from "@/components/common/detail-section";
import { LoadError } from "@/components/common/list-states";
import { ContactList } from "@/components/contacts/contact-list";
import { FindContactsButton } from "@/components/contacts/find-contacts-button";
import { JobCard } from "@/components/jobs/job-card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOptimisticLike } from "@/hooks/use-optimistic-like";
import {
  getCompany,
  setCompanyLiked,
  type CompanyDetail,
} from "@/lib/api/companies";
import type { ContactSearchResult } from "@/lib/api/contacts";
import type { JobCard as JobCardData } from "@/lib/api/jobs";
import { linkedInPeopleUrl } from "@/lib/companies/form";

type LoadState =
  | { status: "loading" }
  | { status: "notFound" }
  | { status: "error"; message: string }
  | { status: "ready"; company: CompanyDetail };

const PAGE_HEADING = "text-2xl font-semibold tracking-tight md:text-3xl";
const COMPANIES_PATH = "/companies";

// Two warm design tokens, as in the inbox lists.
const CARD_BACKGROUNDS = ["bg-surface", "bg-surface-alt"] as const;

/** Friendly page for a company that does not exist (or was deleted). */
export function CompanyNotFound() {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed bg-surface px-6 py-12 text-center">
      <SearchX aria-hidden="true" className="size-8 text-muted-foreground" />
      <h1 className={PAGE_HEADING}>Company not found</h1>
      <p className="max-w-md text-muted-foreground">
        This company may have been deleted. Your other companies are still on
        the Companies page.
      </p>
      <Button asChild variant="outline">
        <Link href={COMPANIES_PATH}>
          <ArrowLeft aria-hidden="true" />
          Back to Companies
        </Link>
      </Button>
    </div>
  );
}

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0]?.toUpperCase())
      .join("") || "?"
  );
}

function ExternalLinkButton({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Button asChild variant="outline">
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
        <ExternalLink aria-hidden="true" />
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    </Button>
  );
}

function CompanyHeader({
  company,
  onChange,
  onDeleted,
}: {
  company: CompanyDetail;
  onChange: (company: CompanyDetail) => void;
  onDeleted: () => void;
}) {
  const save = useCallback(
    (liked: boolean) => setCompanyLiked(company.id, liked),
    [company.id],
  );
  const onSaved = useCallback(
    ({ company: saved }: { company: CompanyDetail }) => onChange(saved),
    [onChange],
  );
  const like = useOptimisticLike({
    liked: company.liked,
    name: company.name,
    save,
    onSaved,
  });

  return (
    <header className="flex flex-col gap-4">
      <Link
        href={COMPANIES_PATH}
        className="inline-flex min-h-11 w-fit items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to Companies
      </Link>
      <div className="flex items-start gap-3">
        {company.logo_url && (
          <Avatar className="size-14 rounded-lg border bg-surface">
            <AvatarImage
              src={company.logo_url}
              alt={`${company.name} logo`}
              className="object-contain"
            />
            <AvatarFallback className="rounded-lg" aria-hidden="true">
              {initials(company.name)}
            </AvatarFallback>
          </Avatar>
        )}
        <h1
          className={`${PAGE_HEADING} min-w-0 flex-1 self-center break-words`}
        >
          {company.name}
        </h1>
        <HeartToggle
          liked={like.liked}
          name={company.name}
          onToggle={like.toggle}
          className="-mr-2"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        {company.website_url && (
          <ExternalLinkButton href={company.website_url}>
            <Globe aria-hidden="true" />
            Website
          </ExternalLinkButton>
        )}
        {company.linkedin_url && (
          <>
            <ExternalLinkButton href={company.linkedin_url}>
              LinkedIn page
            </ExternalLinkButton>
            <ExternalLinkButton href={linkedInPeopleUrl(company.linkedin_url)}>
              People on LinkedIn
            </ExternalLinkButton>
          </>
        )}
      </div>
      <CompanyActions
        company={company}
        detail={company}
        variant="labeled"
        onSaved={onChange}
        onDeleted={onDeleted}
      />
    </header>
  );
}

function AboutSection({ company }: { company: CompanyDetail }) {
  return (
    <DetailSection id="about" title="About" icon={Building2}>
      {company.description?.trim() && (
        <p className="text-sm leading-relaxed break-words whitespace-pre-line text-foreground">
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
          <p className="text-sm leading-relaxed break-words whitespace-pre-line text-foreground">
            {company.history}
          </p>
        </div>
      )}
    </DetailSection>
  );
}

function JobsSection({
  company,
  onJobChange,
}: {
  company: CompanyDetail;
  onJobChange: (job: JobCardData) => void;
}) {
  const count = company.jobs.length;
  return (
    <DetailSection
      id="jobs"
      title="Jobs"
      description={
        count > 0
          ? `${count} ${count === 1 ? "job" : "jobs"}, newest first.`
          : undefined
      }
      icon={Briefcase}
    >
      {count === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed bg-surface px-6 py-8 text-center">
          <Briefcase
            aria-hidden="true"
            className="size-7 text-muted-foreground"
          />
          <p className="font-medium text-foreground">No jobs yet</p>
          <p className="max-w-md text-sm text-muted-foreground">
            Jobs at {company.name} appear here when the daily job search finds
            them.
          </p>
        </div>
      ) : (
        <ul
          aria-label={`Jobs at ${company.name}`}
          className="flex flex-col gap-3"
        >
          {company.jobs.map((job, index) => (
            <JobCard
              key={job.id}
              job={job}
              compact
              onChange={onJobChange}
              className={CARD_BACKGROUNDS[index % CARD_BACKGROUNDS.length]}
            />
          ))}
        </ul>
      )}
    </DetailSection>
  );
}

/**
 * Company Details: the header with like, edit, delete and the LinkedIn links, then the
 * company's details, its jobs and its contacts (Find contacts, and click-to-connect with the
 * newest job's title).
 */
export function CompanyDetails({ companyId }: { companyId: number }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getCompany(companyId, controller.signal)
      .then((result) => {
        if (result.ok) {
          setState({ status: "ready", company: result.company });
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
  }, [companyId, attempt]);

  const update = useCallback((company: CompanyDetail) => {
    setState({ status: "ready", company });
  }, []);

  const updateJob = useCallback((job: JobCardData) => {
    setState((current) =>
      current.status === "ready"
        ? {
            status: "ready",
            company: {
              ...current.company,
              jobs: current.company.jobs.map((existing) =>
                existing.id === job.id ? { ...existing, ...job } : existing,
              ),
            },
          }
        : current,
    );
  }, []);

  // Applied to the current company, so a like or edit saved during the search is kept.
  const updateContacts = useCallback(
    ({ contacts, contact_search }: ContactSearchResult) => {
      setState((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              company: { ...current.company, contacts, contact_search },
            }
          : current,
      );
    },
    [],
  );

  const handleDeleted = useCallback(() => {
    router.push(COMPANIES_PATH);
  }, [router]);

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-4">
        <p role="status" className="text-sm text-muted-foreground">
          Loading company…
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
    return <CompanyNotFound />;
  }

  if (state.status === "error") {
    return (
      <div className="flex flex-col gap-6">
        <h1 className={PAGE_HEADING}>Company details</h1>
        <LoadError
          title="Could not load this company"
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setAttempt((count) => count + 1);
          }}
        />
      </div>
    );
  }

  const { company } = state;
  // Jobs come newest first, so the first one is the most recently discovered.
  const latestJobTitle = company.jobs[0]?.title ?? null;

  return (
    <div className="flex flex-col gap-8">
      <CompanyHeader
        company={company}
        onChange={update}
        onDeleted={handleDeleted}
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:items-start">
        <div className="flex min-w-0 flex-col gap-6">
          <AboutSection company={company} />
          <JobsSection company={company} onJobChange={updateJob} />
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <DetailSection
            id="contacts"
            title="Contacts"
            description="People at this company who could help with a mock interview or a referral."
            icon={UsersRound}
          >
            <FindContactsButton
              companyId={company.id}
              status={company.contact_search}
              onFound={updateContacts}
            />
            <ContactList
              contacts={company.contacts}
              companyName={company.name}
              jobTitle={latestJobTitle}
              contactSearch={company.contact_search}
            />
          </DetailSection>
        </div>
      </div>
    </div>
  );
}
